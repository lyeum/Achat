import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// PIP 마스코트 모드 컴포넌트
// 160×160 캐릭터 아이콘 + 말풍선 (위로 확장)
Item {
    id: pipRoot

    property string fontFamily:     ""
    property string latestMessage:  ""
    property string currentMood:    "neutral"
    property string characterId:    ""      // icons/{id}/{id}.png 경로에 사용
    property bool   inputEnabled:   true
    property bool   bubbleOpen:     false

    // 아이콘/감정 경로 헬퍼
    function _iconUrl()    { return characterId ? Qt.resolvedUrl("../assets/icons/" + characterId + "/" + characterId + ".png") : "" }
    function _emotionUrl() { return characterId ? Qt.resolvedUrl("../assets/icons/" + characterId + "/emotion/" + currentMood + ".png") : "" }

    signal expandRequested()
    signal messageSent(string text)

    // ── 말풍선 영역 (아이콘 위) ──────────────────────────────────────────────
    Rectangle {
        id: bubble
        visible: pipRoot.bubbleOpen
        anchors {
            bottom: iconArea.top
            bottomMargin: 4
            left: parent.left
        }
        width:  230
        height: bubbleCol.implicitHeight + 16
        radius: 10
        color:  "#1E1E1E"
        border.color: "#444"
        border.width: 1

        // 말풍선 꼬리 (삼각형)
        Canvas {
            width: 12; height: 8
            anchors { top: parent.bottom; left: parent.left; leftMargin: 19 }
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.fillStyle = "#444"
                ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(12, 0); ctx.lineTo(6, 8); ctx.closePath(); ctx.fill()
                ctx.fillStyle = "#1E1E1E"
                ctx.beginPath(); ctx.moveTo(1, 0); ctx.lineTo(11, 0); ctx.lineTo(6, 7); ctx.closePath(); ctx.fill()
            }
        }

        ColumnLayout {
            id: bubbleCol
            anchors { fill: parent; margins: 8 }
            spacing: 6

            // 캐릭터 응답 텍스트
            Text {
                Layout.fillWidth: true
                text: pipRoot.latestMessage
                color: "#E0E0E0"
                font.pixelSize: 11
                font.family: pipRoot.fontFamily
                wrapMode: Text.Wrap
                maximumLineCount: 4
                elide: Text.ElideRight
                lineHeight: 1.3
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#333" }

            // 입력 + 버튼 행
            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                // 입력창
                Rectangle {
                    Layout.fillWidth: true
                    height: 26
                    radius: 6
                    color: "#2A2A2A"
                    border.color: pipInput.activeFocus ? "#4A90D9" : "#3A3A3A"
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    TextInput {
                        id: pipInput
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                        verticalAlignment: TextInput.AlignVCenter
                        color: "#E0E0E0"
                        font.pixelSize: 11
                        font.family: pipRoot.fontFamily
                        clip: true
                        enabled: pipRoot.inputEnabled
                        Keys.onReturnPressed: pipRoot._sendInput()

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
                    width: 26; height: 26; radius: 6
                    color: pipRoot.inputEnabled
                           ? (pipSendHover.containsMouse ? "#357ABD" : "#4A90D9")
                           : "#333"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        text: pipRoot.inputEnabled ? "▶" : "…"
                        color: pipRoot.inputEnabled ? "white" : "#666"
                        font.pixelSize: 10
                    }
                    MouseArea {
                        id: pipSendHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: pipRoot.inputEnabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: if (pipRoot.inputEnabled) pipRoot._sendInput()
                    }
                }

                // 풀 창 복귀 버튼 (주황)
                Rectangle {
                    width: 26; height: 26; radius: 6
                    color: pipExpandHover.containsMouse ? "#E09400" : "#F0A500"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text { anchors.centerIn: parent; text: "⤢"; color: "white"; font.pixelSize: 12 }
                    MouseArea {
                        id: pipExpandHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: pipRoot.expandRequested()
                    }
                }
            }
        }
    }

    // ── 캐릭터 아이콘 (160×160 고정) ──────────────────────────────────────────
    Rectangle {
        id: iconArea
        width: 160; height: 160
        anchors { bottom: parent.bottom; left: parent.left }
        radius: 8
        color: "#2A2A2A"
        border.color: iconHover.containsMouse ? "#F0A500" : "#3A3A3A"
        border.width: 1
        Behavior on border.color { ColorAnimation { duration: 150 } }

        // 캐릭터 아이콘 (icons/{id}/{id}.png)
        Image {
            id: pipIcon
            anchors.fill: parent
            anchors.margins: 2
            source: pipRoot._iconUrl()
            fillMode: Image.PreserveAspectFit
            visible: status === Image.Ready
        }

        // 감정 오버레이 (icons/{id}/emotion/{mood}.png)
        Image {
            anchors.fill: parent
            anchors.margins: 2
            source: pipRoot._emotionUrl()
            fillMode: Image.PreserveAspectFit
            visible: status === Image.Ready
        }

        // 에셋 없을 때: mood별 이모지 플레이스홀더
        Text {
            anchors.centerIn: parent
            text: {
                if (pipRoot.currentMood === "happy")        return "😊"
                if (pipRoot.currentMood === "affectionate") return "🥰"
                if (pipRoot.currentMood === "touched")      return "🥹"
                if (pipRoot.currentMood === "curious")      return "🤔"
                if (pipRoot.currentMood === "sad")          return "😢"
                if (pipRoot.currentMood === "embarrassed")  return "😳"
                if (pipRoot.currentMood === "annoyed")      return "😤"
                if (pipRoot.currentMood === "angry")        return "😠"
                return "😐"
            }
            font.pixelSize: 26
            visible: !pipIcon.visible
        }

        MouseArea {
            id: iconHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (!pipRoot.bubbleOpen) {
                    pipRoot.bubbleOpen = true
                    autoClose.restart()
                } else {
                    autoClose.stop()
                    pipRoot.bubbleOpen = false
                }
            }
        }
    }

    // ── 자동 닫힘 타이머 (5초) ──────────────────────────────────────────────
    Timer {
        id: autoClose
        interval: 5000
        repeat: false
        onTriggered: pipRoot.bubbleOpen = false
    }

    // ── 공개 함수 ────────────────────────────────────────────────────────────

    function showBubble(message) {
        latestMessage = message
        bubbleOpen = true
        autoClose.restart()
    }

    function _sendInput() {
        var text = pipInput.text.trim()
        if (text === "") return
        pipInput.text = ""
        autoClose.restart()
        pipRoot.messageSent(text)
    }
}
