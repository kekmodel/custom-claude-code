# 데이터 흐름: req.body가 변경되지 않고 전달되는 과정

## 전체 흐름도

```
Claude Code
    ↓
    ↓ POST /v1/messages
    ↓ req.body = {model, messages, system, tools, ...}
    ↓
[claude-code-router]
    ↓
    ├─→ src/index.ts:160 (preHandler hook)
    │   ├─→ Built-in agents 체크
    │   │   └─→ req.body.tools에 agent 도구 추가 (선택적)
    │   │
    │   └─→ src/utils/router.ts:182 (router 함수)
    │       ├─→ req.body에서 messages, system, tools 읽기
    │       ├─→ 토큰 계산
    │       ├─→ 적절한 모델 선택
    │       └─→ req.body.model만 변경! ← 🎯 여기가 핵심!
    │
    ├─→ @musistudio/llms (Server 클래스)
    │   ├─→ req.body 전체를 받음
    │   ├─→ Transformer 적용
    │   │   ├─→ messages 변환 (Anthropic → Provider 형식)
    │   │   ├─→ system 변환
    │   │   ├─→ tools 변환
    │   │   └─→ 기타 매개변수 변환
    │   │
    │   ├─→ 실제 LLM API 호출 (DeepSeek, Gemini, 등)
    │   │   POST https://api.deepseek.com/chat/completions
    │   │   Body: 변환된 요청
    │   │
    │   └─→ 응답 변환 (Provider 형식 → Anthropic 형식)
    │
    ├─→ src/index.ts:200 (onSend hook)
    │   └─→ SSE 스트림 처리 (Built-in agent 도구 호출 처리)
    │
    ↓
    ↓ Anthropic Messages API 형식 응답
    ↓
Claude Code
```

## 코드로 보는 데이터 흐름

### 1단계: 요청 받기 (src/index.ts:160)

```typescript
server.addHook("preHandler", async (req, reply) => {
  if (req.url.startsWith("/v1/messages")) {
    // 이 시점의 req.body:
    // {
    //   model: "claude-sonnet-4",
    //   messages: [...],
    //   system: [...],
    //   tools: [...]
    // }

    // Built-in agents 추가 (선택적)
    for (const agent of agentsManager.getAllAgents()) {
      if (agent.shouldHandle(req, config)) {
        // ✅ tools 배열에 agent 도구 추가
        req.body.tools.unshift(...agent.tools);
      }
    }

    // 라우터 호출
    await router(req, reply, { config, event });

    // 이 시점의 req.body:
    // {
    //   model: "deepseek,deepseek-chat",  ← 변경됨!
    //   messages: [...],  ← 그대로!
    //   system: [...],    ← 그대로!
    //   tools: [...]      ← agent 도구가 추가되었을 수 있음
    // }
  }
});
```

### 2단계: 모델 선택 (src/utils/router.ts:182)

```typescript
export const router = async (req: any, _res: any, context: any) => {
  const { config, event } = context;

  // ✅ destructure하지만 수정하지 않음!
  const { messages, system = [], tools } = req.body;

  // 토큰 계산
  const tokenCount = calculateTokenCount(messages, system, tools);
  // 예: 45000 토큰

  // 모델 선택 로직
  let model;
  if (config.CUSTOM_ROUTER_PATH) {
    // 커스텀 라우터가 있으면 사용
    const customRouter = require(config.CUSTOM_ROUTER_PATH);
    model = await customRouter(req, config, { event });
  }

  if (!model) {
    // 기본 라우터 로직
    model = await getUseModel(req, tokenCount, config);
    // 반환값: "deepseek,deepseek-chat"
  }

  // ⚠️ 오직 model 필드만 변경!
  req.body.model = model;

  // messages, system, tools는 전혀 건드리지 않음!
  // req.body.messages = messages;  ← 이런 코드 없음!
  // req.body.system = system;      ← 이런 코드 없음!
  // req.body.tools = tools;        ← 이런 코드 없음!
};
```

### 3단계: @musistudio/llms 처리

```typescript
// @musistudio/llms 내부 (개념적 코드)
class Server {
  async handleRequest(req: FastifyRequest) {
    // req.body를 그대로 받음
    const { model, messages, system, tools, ...rest } = req.body;

    // 1. Provider 찾기
    const [providerName, modelName] = model.split(",");
    const provider = this.config.providers.find(p => p.name === providerName);

    // 2. Transformer 적용
    const transformer = this.getTransformer(provider, modelName);

    // Anthropic 형식 → Provider 형식 변환
    const transformedRequest = await transformer.transformRequest({
      model: modelName,
      messages,  // ← 원본 그대로 전달됨
      system,    // ← 원본 그대로 전달됨
      tools,     // ← 원본 그대로 전달됨
      ...rest
    });

    // DeepSeek 예시:
    // {
    //   model: "deepseek-chat",
    //   messages: [
    //     {role: "system", content: system 배열을 문자열로 합침},
    //     {role: "user", content: "..."},
    //     {role: "assistant", content: "..."}
    //   ],
    //   tools: [
    //     {type: "function", function: {name: "Read", ...}}
    //   ]
    // }

    // 3. 실제 API 호출
    const response = await fetch(provider.api_base_url, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${provider.api_key}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(transformedRequest)
    });

    // 4. 응답 변환 (Provider 형식 → Anthropic 형식)
    const providerResponse = await response.json();
    const transformedResponse = await transformer.transformResponse(providerResponse);

    // Anthropic 형식으로 반환:
    // {
    //   id: "msg_xxx",
    //   type: "message",
    //   role: "assistant",
    //   content: [{type: "text", text: "..."}],
    //   model: "deepseek-chat",
    //   usage: {input_tokens: 100, output_tokens: 50}
    // }

    return transformedResponse;
  }
}
```

### 4단계: 응답 반환 (src/index.ts:200)

```typescript
server.addHook("onSend", (req, reply, payload, done) => {
  if (req.url.startsWith("/v1/messages")) {
    // payload는 Anthropic 형식의 응답
    // Claude Code가 이해할 수 있는 형식으로 이미 변환됨

    // Built-in agent 처리가 필요한 경우 SSE 스트림 재작성
    if (req.agents) {
      // 스트림을 파싱하고 agent 도구 호출을 처리한 후
      // 다시 Anthropic 형식으로 직렬화
      return done(null, rewriteStream(...));
    }

    // 그대로 반환
    done(null, payload);
  }
});
```

## 핵심 요약

### ✅ 변경되는 것
- `req.body.model`: "claude-sonnet-4" → "deepseek,deepseek-chat"
- `req.body.tools`: Built-in agent 도구가 추가될 수 있음 (선택적)

### ✅ 변경되지 않는 것
- `req.body.messages`: 대화 히스토리 그대로
- `req.body.system`: 시스템 프롬프트 그대로
- `req.body.tools`: 원본 도구 목록 (agent 도구 제외)
- `req.body.thinking`: Thinking 설정 그대로
- `req.body.metadata`: 메타데이터 그대로
- `req.body.max_tokens`: 토큰 제한 그대로

### 🔄 Transformer의 역할
@musistudio/llms의 Transformer가 Provider별로 형식을 변환:

```
Anthropic Format              DeepSeek Format
─────────────────            ─────────────────
messages: [                  messages: [
  {role: "user",               {role: "system", content: "..."},
   content: "..."}             {role: "user", content: "..."}
]                            ]
system: [...]                (system이 messages에 합쳐짐)
tools: [                     tools: [
  {name: "Read",               {type: "function",
   input_schema: {...}}         function: {name: "Read", ...}}
]                            ]
```

## 실제 확인 방법

```bash
# 1. 빌드
npm run build

# 2. 디버깅 코드 추가 (src/utils/router.ts)
export const router = async (req: any, _res: any, context: any) => {
  console.log("=== BEFORE ===");
  console.log("Model:", req.body.model);
  console.log("Messages:", JSON.stringify(req.body.messages).slice(0, 100));

  // ... 라우팅 로직 ...
  req.body.model = model;

  console.log("=== AFTER ===");
  console.log("Model:", req.body.model);
  console.log("Messages (unchanged):", JSON.stringify(req.body.messages).slice(0, 100));
};

# 3. 재시작
ccr restart

# 4. 테스트
ccr code "안녕하세요"

# 5. 로그 확인
tail -f ~/.claude-code-router/logs/ccr-*.log
```

## 왜 이렇게 설계되었나?

1. **최소 침습적**: Claude Code의 동작을 최소한으로만 변경
2. **투명성**: Claude Code는 자신이 다른 LLM을 사용한다는 것을 모름
3. **호환성**: Anthropic Messages API와 100% 호환
4. **확장성**: Transformer 패턴으로 새로운 Provider 쉽게 추가 가능
