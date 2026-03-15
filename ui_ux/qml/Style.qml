pragma Singleton
import QtQuick 2.15

QtObject {
    // ── 색상 ─────────────────────────────────────────────────────────────────
    readonly property color bgWindow:        "#1E1E2E"   // 메인 윈도우 배경
    readonly property color bgBubble:        "#2A2A3E"   // 채팅창 배경
    readonly property color bubbleUser:      "#4A90D9"   // 사용자 말풍선
    readonly property color bubbleAssistant: "#3A3A4E"   // 어시스턴트 말풍선
    readonly property color bubbleSystem:    "#444455"   // 시스템 메시지

    readonly property color textPrimary:     "#EAEAF2"   // 본문
    readonly property color textSecondary:   "#9090A8"   // 보조 텍스트 (시간, 힌트)
    readonly property color accent:          "#7C6AF7"   // 강조 (전송 버튼, 활성 탭)
    readonly property color accentHover:     "#9B8FFA"
    readonly property color inputBg:         "#2E2E42"
    readonly property color border:          "#3A3A52"

    // ── 폰트 ─────────────────────────────────────────────────────────────────
    readonly property string fontFamily:     "Noto Sans KR, Segoe UI, sans-serif"
    readonly property int    fontSizeBase:   14
    readonly property int    fontSizeSmall:  12
    readonly property int    fontSizeLarge:  16

    // ── 간격 / 반지름 ─────────────────────────────────────────────────────────
    readonly property int radiusBubble:  16
    readonly property int radiusInput:   12
    readonly property int radiusWindow:  18
    readonly property int paddingBase:   12
    readonly property int paddingSmall:   8

    // ── 애니메이션 ────────────────────────────────────────────────────────────
    readonly property int durationFast:   120   // ms — hover, opacity
    readonly property int durationNormal: 220   // ms — 윈도우 크기 전환
    readonly property int durationSlow:   380   // ms — bubble ↔ full 전환

    // ── 불투명도 ──────────────────────────────────────────────────────────────
    readonly property real opacityIdle:   0.85   // 포커스 아웃 시
    readonly property real opacityActive: 1.0    // 포커스 인 시

    // ── 크기 ─────────────────────────────────────────────────────────────────
    readonly property int bubbleSize:     72
    readonly property int windowWidth:    360
    readonly property int windowHeight:   520
}
