import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// PIP 마스코트 모드
// ─ 캐릭터 이미지만 투명 배경으로 표시
// ─ 응답 말풍선: 캐릭터 위에 독립적으로 표시 (입력창과 분리)
// ─ 입력창: 캐릭터 클릭 시에만 표시
// ─ bubbleDirection: "random" | "left" | "right" (꼬리 위치)
Item {
    id: pipRoot

    property string fontFamily:       ""
    property string latestMessage:    ""
    property string currentMood:      "neutral"
    property string characterId:      ""
    property string partsJson:        "{}"
    property bool   inputEnabled:     true
    property bool   bubbleOpen:       false
    property int    iconVersion:      0
    property string bubbleDirection:  "random"   // "random" | "left" | "right"

    // 입력창 표시 여부 (외부에서도 읽을 수 있도록 public)
    property bool inputOpen:   false
    property bool isSleeping:  false   // bridge.sleepStateChanged 로 갱신

    signal sleepRequested()
    signal wakeRequested()

    // ── 내부 상태 ────────────────────────────────────────────────────────────
    property bool _tailLeft: true    // 꼬리 위치: true=왼쪽, false=오른쪽

    // 파츠 JSON 파싱
    readonly property var  _p:          { try { return JSON.parse(partsJson) } catch(e) { return {} } }
    readonly property bool _hasAnyPart: !!_p.base || !!_p.hair || !!_p.eye || !!_p.eyebrow
                                     || !!_p.nose || !!_p.mouth || !!_p.emotion || !!_p.cloth

    // 목표 창 높이 (main.qml 의 resizeRequested 로 전달)
    readonly property int _desiredHeight: {
        var h = 160
        if (bubbleOpen) h += 8 + 178    // 말풍선 영역(최대 178px)
        if (inputOpen)  h += 8 + 46     // 입력 바
        return h
    }

    // 아이콘/감정/파츠 경로 헬퍼
    function _iconUrl()    { return characterId ? Qt.resolvedUrl("../assets/icons/" + characterId + "/" + characterId + ".png") + "#v" + iconVersion : "" }
    function _emotionUrl() { return characterId ? Qt.resolvedUrl("../assets/icons/" + characterId + "/emotion/" + currentMood + ".png") : "" }
    function _partUrl(type, file) {
        if (!file) return ""
        return Qt.resolvedUrl("../assets/characters/" + type + "/" + file)
    }

    signal expandRequested()
    signal messageSent(string text)
    signal resizeRequested(int h)

    // 목표 높이 변화 → 창 리사이즈 요청
    on_DesiredHeightChanged: resizeRequested(_desiredHeight)

    // 말풍선 열릴 때 꼬리 방향 결정
    onBubbleOpenChanged: {
        if (bubbleOpen) {
            if (bubbleDirection === "left")       _tailLeft = true
            else if (bubbleDirection === "right") _tailLeft = false
            else                                  _tailLeft = (Math.random() < 0.5)
            // 입력 중이 아닐 때만 자동 닫힘 타이머 시작
            if (!inputOpen) autoClose.restart()
        } else {
            autoClose.stop()
        }
    }

    // 입력창 열고 닫힐 때 자동 닫힘 타이머 제어
    onInputOpenChanged: {
        if (inputOpen) {
            autoClose.stop()
        } else if (bubbleOpen) {
            autoClose.restart()
        }
    }

    // ── 말풍선 (캐릭터 위, 메시지 전용) ─────────────────────────────────────
    Rectangle {
        id: bubble
        visible: pipRoot.bubbleOpen

        width: 238
        // 내용 높이에 맞추되 최대 178px
        height: Math.min(msgFlick.height + 20, 178)

        anchors {
            bottom: pipRoot.inputOpen ? inputBar.top : charArea.top
            bottomMargin: 8
            // 꼬리 방향에 따라 좌/우 정렬
            left:  pipRoot._tailLeft  ? parent.left  : undefined
            right: !pipRoot._tailLeft ? parent.right : undefined
        }

        color: "#1C1C1C"
        border.color: "#484848"
        border.width: 1
        radius: 10

        // 말풍선 꼬리 (아래 방향 삼각형)
        Canvas {
            id: bubbleTail
            width: 14; height: 9
            anchors {
                top: parent.bottom
                left:  pipRoot._tailLeft  ? parent.left  : undefined
                right: !pipRoot._tailLeft ? parent.right : undefined
                leftMargin:  pipRoot._tailLeft  ? 18 : 0
                rightMargin: !pipRoot._tailLeft ? 18 : 0
            }
            property bool tailLeft: pipRoot._tailLeft
            onTailLeftChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.fillStyle = "#484848"
                ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo(14,0); ctx.lineTo(7,9); ctx.closePath(); ctx.fill()
                ctx.fillStyle = "#1C1C1C"
                ctx.beginPath(); ctx.moveTo(1,0); ctx.lineTo(13,0); ctx.lineTo(7,8); ctx.closePath(); ctx.fill()
            }
        }

        // 메시지 텍스트 (스크롤 가능)
        Flickable {
            id: msgFlick
            anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 10; bottomMargin: 10; leftMargin: 10; rightMargin: 10 }
            // 두 문장 기준 약 110px, 최대 150px
            height: Math.min(msgText.implicitHeight, 150)
            clip: true
            contentHeight: msgText.implicitHeight
            contentWidth: width
            flickableDirection: Flickable.VerticalFlick
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height

            ScrollBar.vertical: ScrollBar {
                policy: msgFlick.contentHeight > msgFlick.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                width: 4
            
    contentItem: Rectangle { color: "transparent" }
    background: Rectangle { color: "transparent" }
}

            Text {
                id: msgText
                width: msgFlick.width - (msgFlick.contentHeight > msgFlick.height ? 8 : 0)
                text: pipRoot.latestMessage
                color: "#E0E0E0"
                font.pixelSize: 12
                font.family: pipRoot.fontFamily
                wrapMode: Text.Wrap
                lineHeight: 1.4
            }
        }

        // 마우스 휠 스크롤 지원
        WheelHandler {
            target: msgFlick
            property: "contentY"
            rotationScale: 2
        }
    }

    // ── 입력 바 (캐릭터 클릭 시에만 표시) ───────────────────────────────────
    Rectangle {
        id: inputBar
        visible: pipRoot.inputOpen

        width: 238
        height: 46

        anchors {
            bottom: charArea.top
            bottomMargin: 8
            left: parent.left
        }

        color: "#1A1A1A"
        border.color: "#484848"
        border.width: 1
        radius: 8

        RowLayout {
            anchors { fill: parent; leftMargin: 8; rightMargin: 8; topMargin: 8; bottomMargin: 8 }
            spacing: 5

            // 입력창
            Rectangle {
                Layout.fillWidth: true
                height: 28
                radius: 6
                color: "#252525"
                border.color: pipInput.activeFocus ? "#4A90D9" : "#3A3A3A"
                Behavior on border.color { ColorAnimation { duration: 120 } }

                TextInput {
                    id: pipInput
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    verticalAlignment: TextInput.AlignVCenter
                    color: "#E0E0E0"
                    font.pixelSize: 12
                    font.family: pipRoot.fontFamily
                    clip: true
                    enabled: pipRoot.inputEnabled
                    Keys.onReturnPressed: pipRoot._sendInput()
                    onActiveFocusChanged: {
                        if (activeFocus)  autoClose.stop()
                        else if (pipRoot.bubbleOpen) autoClose.restart()
                    }

                    Text {
                        anchors.fill: parent
                        verticalAlignment: Text.AlignVCenter
                        text: "입력..."
                        color: "#555"
                        font: pipInput.font
                        visible: pipInput.text === "" && !pipInput.activeFocus
                    }
                }
            }

            // 전송 버튼
            Rectangle {
                width: 28; height: 28; radius: 6
                color: pipRoot.inputEnabled
                       ? (pipSendHov.containsMouse ? "#357ABD" : "#4A90D9")
                       : "#333"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: pipRoot.inputEnabled ? "▶" : "…"; color: pipRoot.inputEnabled ? "white" : "#666"; font.pixelSize: 10 }
                MouseArea {
                    id: pipSendHov
                    anchors.fill: parent; hoverEnabled: true
                    cursorShape: pipRoot.inputEnabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: if (pipRoot.inputEnabled) pipRoot._sendInput()
                }
            }

            // 풀창 복귀 버튼
            Rectangle {
                width: 28; height: 28; radius: 6
                color: pipExpandHov.containsMouse ? "#E09400" : "#F0A500"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "⤢"; color: "white"; font.pixelSize: 12 }
                MouseArea {
                    id: pipExpandHov
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: pipRoot.expandRequested()
                }
            }
        }
    }

    // ── 캐릭터 영역 (투명 배경) ──────────────────────────────────────────────
    Item {
        id: charArea
        width: 160; height: 160
        anchors { bottom: parent.bottom; left: parent.left }
        opacity: pipRoot.isSleeping ? 0.35 : 1.0
        Behavior on opacity { NumberAnimation { duration: 400 } }

        // 기본 아이콘 (icons/{id}/{id}.png)
        Image {
            id: pipIcon
            anchors.fill: parent
            source: pipRoot._iconUrl()
            fillMode: Image.PreserveAspectFit
            cache: false
            smooth: true; mipmap: true
            visible: status === Image.Ready
        }

        // 파츠 합성 폴백: base → eye → eyebrow → nose → mouth → emotion → hair → cloth
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("base",    pipRoot._p.base    || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("eye",     pipRoot._p.eye     || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("eyebrow", pipRoot._p.eyebrow || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("nose",    pipRoot._p.nose    || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("mouth",   pipRoot._p.mouth   || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("emotion", pipRoot._p.emotion || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("hair",    pipRoot._p.hair    || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }
        Image { anchors.fill: parent; source: !pipIcon.visible ? pipRoot._partUrl("cloth",   pipRoot._p.cloth   || "") : ""; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; visible: status === Image.Ready }

        // 감정 오버레이
        Image {
            anchors.fill: parent
            source: pipRoot._emotionUrl()
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true
            visible: status === Image.Ready
        }

        // 이모지 플레이스홀더 (아이콘도 파츠도 없을 때)
        Text {
            anchors.centerIn: parent
            text: {
                if (pipRoot.currentMood === "happy")        return "😊"
                if (pipRoot.currentMood === "affectionate") return "😍"
                if (pipRoot.currentMood === "touched")      return "😭"
                if (pipRoot.currentMood === "curious")      return "🤔"
                if (pipRoot.currentMood === "sad")          return "😢"
                if (pipRoot.currentMood === "embarrassed")  return "😳"
                if (pipRoot.currentMood === "annoyed")      return "😤"
                if (pipRoot.currentMood === "angry")        return "😠"
                return "😐"
            }
            font.pixelSize: 28
            font.family: "Segoe UI Emoji, Segoe UI Symbol, Apple Color Emoji, Noto Color Emoji"
            renderType: Text.QtRendering
            visible: !pipIcon.visible && !pipRoot._hasAnyPart
        }

        // 클릭: 입력창 토글 (절전 중이면 깨우기)
        MouseArea {
            id: iconHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                sleepTimer.restart()
                if (pipRoot.isSleeping) {
                    pipRoot.wakeRequested()
                    return
                }
                pipRoot.inputOpen = !pipRoot.inputOpen
                if (pipRoot.inputOpen) {
                    Qt.callLater(() => pipInput.forceActiveFocus())
                }
            }
        }

    }

    // ── 절전 안내 (charArea 위에 겹쳐 표시, charArea opacity 와 분리) ─────────
    Item {
        visible: pipRoot.isSleeping
        width: charArea.width; height: charArea.height
        anchors { bottom: parent.bottom; left: parent.left }
        z: 5

        Column {
            anchors.centerIn: parent
            spacing: 4
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "💤"
                font.pixelSize: 26
                renderType: Text.QtRendering
                font.family: "Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji"
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "절전 중"
                color: "#D0D0D0"; font.pixelSize: 11
                font.family: pipRoot.fontFamily
            }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                sleepTimer.restart()
                pipRoot.wakeRequested()
            }
        }
    }

    // ── 자동 닫힘 타이머 ─────────────────────────────────────────────────────
    Timer {
        id: autoClose
        interval: 5000
        repeat: false
        onTriggered: {
            pipRoot.bubbleOpen = false
            pipRoot.inputOpen = false
        }
    }

    // ── 절전 타이머 (5분 비활동 시 절전 요청) ─────────────────────────────────
    Timer {
        id: sleepTimer
        interval: 300000   // 5분
        repeat: false
        running: pipRoot.visible && !pipRoot.isSleeping
        onTriggered: {
            if (!pipRoot.inputOpen)
                pipRoot.sleepRequested()
        }
    }

    // ── 공개 함수 ────────────────────────────────────────────────────────────
    function showBubble(message) {
        latestMessage = message
        bubbleOpen = true
        // bubbleOpen 변경이 onBubbleOpenChanged를 통해 타이머 처리
    }

    function _sendInput() {
        var text = pipInput.text.trim()
        if (text === "") return
        pipInput.text = ""
        autoClose.restart()
        sleepTimer.restart()
        pipRoot.messageSent(text)
    }
}
