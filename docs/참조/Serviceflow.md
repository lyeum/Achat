# Achat 서비스 플로우 차트

> Mermaid 렌더링: GitHub / [Mermaid Live Editor](https://mermaid.live) / VS Code Mermaid Preview

---

## 1. 앱 시작 플로우

```mermaid
flowchart TD
    A([Achat.exe 실행]) --> B{uv.exe 존재?}
    B -- No --> ERR1[MessageBox 오류 안내\n재설치 요청]
    B -- Yes --> C{model_q4km.gguf 존재?}
    C -- No --> ERR2[MessageBox 안내\nmodels/ 에 파일 복사 요청]
    C -- Yes --> D[ACHAT_ENV=deploy 설정]
    D --> E[uv run python main.py]

    E --> F[torch 선로드\nVRAM 확인]
    F --> G[QQmlApplicationEngine 초기화\nChatBridge 등록]
    G --> H[rag/index.py\nworld_knowledge 컬렉션 존재 여부 확인]
    H -- 없음 --> I[Seaside.md 청킹\nChromaDB 인덱싱]
    H -- 있음 --> J[스킵]
    I --> J
    J --> K[SessionManager 초기화\n마지막 세션 복원]
    K --> L[Agent 초기화\nLLMClient 모델 로드]
    L --> M([플로팅 윈도우 표시\n대화 대기])
```

---

## 2. 대화 한 턴 (Chat Mode) 시퀀스

```mermaid
sequenceDiagram
    actor User
    participant QML as main.qml
    participant Bridge as ChatBridge
    participant Worker as LLMWorker
    participant Router as ConversationRouter
    participant Builder as PromptBuilder
    participant Mem as Memory
    participant RAG as RAG
    participant LLM as LLMClient
    participant VDB as ChromaDB

    User->>QML: 텍스트 입력 + 전송
    QML->>Bridge: sendMessage(text) [Slot]
    Bridge->>Worker: LLMWorker 생성 + start()
    Bridge-->>QML: statusChanged("thinking") [Signal]

    Worker->>Router: handle_turn(user_input, mode="chat")

    Note over Router: 0. 장소 이동 감지
    Router->>RAG: detect_move_intent(user_input)
    RAG-->>Router: place_narration (있으면)

    Note over Router: 1~3. 컨텍스트 수집
    Router->>Mem: short_term.get_recent(session) → 최근 5턴
    Router->>VDB: long_term.query(user_input, char_id)
    VDB-->>Router: 유사 기억 top-2 (cosine ≥ 0.52)
    Router->>RAG: WorldRetriever.query(user_input)
    RAG->>VDB: world_knowledge cosine 검색
    VDB-->>RAG: 세계관 청크 top-2
    RAG-->>Router: rag_results

    Note over Router: 4. Context Assembly
    Router->>Builder: assemble(short_buf, vdb_results, rag_results, user_input)
    Builder-->>Router: messages [Layer A~F + user]

    Note over Router: 4-1. 나레이션 트리거 체크
    Router->>Router: _check_world_triggers() / NarrationMonitor.check_keyword()
    Router->>Router: _pending_narration 저장

    Note over Router: 5. LLM 추론
    Router->>LLM: generate(messages, stream=True)
    LLM-->>Router: response (str)

    Note over Router: 6. 상태 업데이트
    Router->>Router: check_trigger_events() → mood / affection
    Router->>Router: _PROMISE_RE → character_notes 추가

    Note over Router: 7. 세션 기록
    Router->>Mem: session.add_turn(user_input, response)
    Router->>Mem: short_term.evict_to_context(session)

    Note over Router: 8. 요약 트리거 (비동기)
    Router->>Router: check_trigger() [매 5턴]
    Router-->>Mem: Thread(_run_summarizer) [백그라운드]
    Mem->>LLM: summarize(dialogue_log) → 요약 텍스트
    Mem->>Mem: score_importance() → 0.0 / 0.60 / 0.85
    alt score ≥ 0.65
        Mem->>VDB: long_term.store() → upsert
    end

    Router-->>Worker: response

    Worker-->>Bridge: response_ready(response) [Signal]
    Bridge->>Bridge: _split_narration() 파싱
    alt _pending_narration 있음
        Bridge-->>QML: messageAdded(narrator bubble) [Signal]
    end
    Bridge-->>QML: messageAdded(assistant bubble) [Signal]
    Bridge-->>QML: statusChanged("idle") [Signal]
    QML-->>User: 말풍선 표시
```

---

## 3. 기능 모드 플로우

```mermaid
flowchart TD
    A([사용자 기능 모드 입력]) --> B[Agent.handle_input\nmode=function]
    B --> C[도구 선택\nselect_tool]

    C --> D{도구 종류}
    D -->|폴더 정리| E[FolderClassifier\n자연어 → JSON 파싱\nLLM 호출]
    D -->|확장자 변환| F[FolderConverter\n이미지·문서 포맷 변환\nPillow / ffmpeg]
    D -->|이름 변경| G[FolderRenamer\n패턴 규칙 적용]
    D -->|프롬프트 변환| H[PromptConverter\n기능 전용 시스템 프롬프트\nLLM 호출]
    D -->|로컬 검색| I[LocalSearch\nSQLite FTS5 인덱싱 + MATCH]

    E --> J[tool.execute(params)\nrule-based 실행]
    F --> J
    G --> J
    H --> J
    I --> J

    J --> K[작업 결과 텍스트 반환]
    K --> L[Router.handle_turn\nrecent_ops 주입\nmode=chat 1턴]
    L --> M([캐릭터가 수행 내용 자연어로 안내])
```

---

## 4. 메모리 파이프라인 플로우

```mermaid
flowchart LR
    subgraph SESSION["세션 내"]
        A["사용자 발화"]
        B["단기 메모리\nshort_term\n최근 5턴 슬라이딩"]
        C["session_context\nevict_to_context()\n5턴 초과 분 누적"]
        D["character_notes\n약속 패턴 ~할게\n~기억할게"]
    end

    subgraph VDB_WRITE["장기 메모리 쓰기 (매 5턴, 백그라운드)"]
        E["summarize()\n최근 20개 메시지\n→ LLM 1~3문장 요약"]
        F{"score_importance()"}
        G["high 0.85\n이름·약속·비밀·고마워"]
        H["mid 0.60\n취미·감정·저번에"]
        I["low 0.0\n키워드 없음 → 저장 안 함"]
        J["ChromaDB upsert\ncosine 0.85 중복 제거\nquota 200개 상한\nTTL 30일"]
    end

    subgraph VDB_READ["장기 메모리 읽기 (매 턴)"]
        K["long_term.query(user_input)\nbge-m3 임베딩\ncosine threshold 0.52"]
        L["유사 기억 top-2\n→ Layer C 주입"]
    end

    A --> B
    B -->|5턴 초과| C
    A --> D

    B --> E
    E --> F
    F -->|high| G --> J
    F -->|mid| H --> J
    F -->|low| I

    J --> K
    K --> L
```

---

## 5. 세션 관리 플로우

```mermaid
flowchart TD
    A([앱 시작]) --> B[SessionManager.get_active()]
    B --> C{마지막 세션 있음?}
    C -- Yes --> D[_restore_session_from_state()\nセッションstate 복원\ndialogue 로드]
    C -- No --> E[new_session(char_id)\n새 세션 생성]

    D --> F([대화 시작])
    E --> F

    F --> G{UI 조작}
    G -->|캐릭터 변경| H[switchSession(new_char_id)\n또는 newSession()]
    G -->|현재 대화 초기화| I[resetSession()\ndialogue_log 삭제\nVDB 장기기억 유지]
    G -->|세션 삭제| J[delete_session()\nVDB 에피소딕 삭제 가능]
    G -->|앱 종료| K[_sync_session_state()\nsession_state.json 스냅샷 저장]

    H --> L[swap_persona()\n캐릭터 YAML 재로드\nAgent 재초기화]
    L --> F
    I --> F
```

---

## 6. CD 배포 파이프라인 플로우

```mermaid
flowchart TD
    A([git tag v0.1.0\ngit push origin v0.1.0]) --> B[GitHub Actions CD 트리거]

    B --> TAG["tag-name job\n태그명 추출"]

    TAG --> ZIP["package-zip job\n(Ubuntu)"]
    TAG --> INST["package-installer job\n(Windows)"]

    subgraph ZIP_STEPS["package-zip 단계"]
        Z1["actions/checkout"]
        Z2["astral-sh/setup-uv"]
        Z3["scripts/package_deploy.sh\nrsync → dist/achat/\nzip → dist/achat.zip"]
        Z1 --> Z2 --> Z3
    end

    subgraph INST_STEPS["package-installer 단계"]
        I1["actions/checkout"]
        I2["actions/setup-python 3.11"]
        I3["choco install innosetup"]
        I4["uv.exe 다운로드"]
        I5["python -m pip install pyinstaller\npython -m PyInstaller achat.spec\n→ Achat.exe"]
        I6["ISCC achat_setup.iss\n→ AchatSetup.exe"]
        I1 --> I2 --> I3 --> I4 --> I5 --> I6
    end

    ZIP --> ZIP_STEPS
    INST --> INST_STEPS

    ZIP_STEPS --> REL["release job\nupload-artifact 수집\nsoftprops/action-gh-release\n→ GitHub Release 생성"]
    INST_STEPS --> REL

    REL --> PUB(["GitHub Release\n─────────────\nAchatSetup.exe\nachat.zip"])
```
