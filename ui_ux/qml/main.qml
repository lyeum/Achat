import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Window {
    id: root

    // ── 크기 / 상태 ─────────────────────────────────────────────────────────
    property bool isBubble: false
    property string currentMode: "chat"   // "chat" | "function"

    width:  isBubble ? 72  : 360
    height: isBubble ? 72  : 520
    flags:  Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color:  "transparent"
    visible: true
    title:  "Achat"

    // 첫 렌더링 후 우하단 배치
    Component.onCompleted: {
        x = Screen.width  - width  - 40
        y = Screen.height - height - 60
    }

    Behavior on width  { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }
    Behavior on height { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }

    // taskbar X 또는 Alt+F4 → 앱 완전 종료
    onClosing: Qt.quit()

    // ── 전체 창 드래그 (OS 네이티브 — 버튼 이벤트 가로채지 않음) ─────────
    DragHandler {
        id: dragHandler
        target: null
        onActiveChanged: if (active) root.startSystemMove()
    }

    // ── hover 투명도 (HoverHandler — 이벤트 가로채지 않음) ────────────────
    HoverHandler { id: windowHover }
    opacity: windowHover.hovered || isBubble ? 1.0 : 0.85
    Behavior on opacity { NumberAnimation { duration: 300 } }

    // ── 한글 폰트 (Windows 폰트 경로에서 로드) ───────────────────────────
    FontLoader {
        id: koreanFont
        source: "file:///mnt/c/Windows/Fonts/malgun.ttf"
    }

    // ── 브리지 이벤트 수신 ───────────────────────────────────────────────
    Connections {
        target: bridge

        function onMessageAdded(role, content) {
            messageModel.append({ "role": role, "content": content })
            Qt.callLater(() => { chatList.positionViewAtEnd() })
        }

        function onStatusChanged(status) {
            sendBtn.enabled = (status === "ready")
            inputField.enabled = (status === "ready")
            if (status === "thinking") {
                messageModel.append({ "role": "assistant", "content": "..." })
            } else {
                if (messageModel.count > 0) {
                    var last = messageModel.get(messageModel.count - 1)
                    if (last.content === "...") messageModel.remove(messageModel.count - 1)
                }
            }
        }

        function onCharacterNameChanged(name) {
            // 바인딩 대신 직접 할당하지 않음 — charNameLabel.text 바인딩이 처리
        }
    }

    // ── 메시지 모델 ──────────────────────────────────────────────────────
    ListModel { id: messageModel }

    // ── 메인 컨테이너 ────────────────────────────────────────────────────
    Rectangle {
        id: container
        anchors.fill: parent
        radius: root.isBubble ? width / 2 : 16
        color:  root.isBubble ? "#4A90D9" : "#1E1E1E"
        clip:   true

        Behavior on radius { NumberAnimation { duration: 200 } }
        Behavior on color  { ColorAnimation  { duration: 200 } }

        // ── 버블 모드: 캐릭터 이니셜 + 더블클릭으로 확장 ────────────────
        Text {
            anchors.centerIn: parent
            visible: root.isBubble
            text: bridge ? bridge.characterName.charAt(0).toUpperCase() : ""
            color: "white"
            font.pixelSize: 28
            font.bold: true
        }
        MouseArea {
            anchors.fill: parent
            visible: root.isBubble
            onDoubleClicked: root.isBubble = false
        }

        // ── 확장 모드 ────────────────────────────────────────────────────
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            visible: !root.isBubble

            // 타이틀바 (드래그 영역)
            Rectangle {
                id: titleBar
                Layout.fillWidth: true
                height: 38
                color: "#2A2A2A"
                radius: 16


                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 8 }

                    Text {
                        id: charNameLabel
                        text: bridge ? bridge.characterName : ""
                        color: "#E0E0E0"
                        font.pixelSize: 13
                        font.bold: true
                        font.family: koreanFont.font.family
                    }

                    Item { Layout.fillWidth: true }

                    // 버블 축소 버튼
                    Rectangle {
                        width: 20; height: 20; radius: 10
                        color: bubbleHover.containsMouse ? "#E09400" : "#F0A500"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text { anchors.centerIn: parent; text: "●"; color: "white"; font.pixelSize: 9 }
                        MouseArea {
                            id: bubbleHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.isBubble = true
                        }
                    }

                    // 닫기 버튼
                    Rectangle {
                        width: 20; height: 20; radius: 10
                        color: closeHover.containsMouse ? "#C03030" : "#E05050"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                        MouseArea {
                            id: closeHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.quit()
                        }
                    }
                }
            }

            // 모드 전환 바
            Rectangle {
                Layout.fillWidth: true
                height: 32
                color: "#252525"

                RowLayout {
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    spacing: 6

                    Repeater {
                        model: [{ label: "대화", mode: "chat" }, { label: "기능", mode: "function" }]

                        Rectangle {
                            Layout.fillWidth: true
                            height: 22
                            radius: 6
                            color: root.currentMode === modelData.mode ? "#4A90D9" : "#3C3C3C"
                            Behavior on color { ColorAnimation { duration: 150 } }

                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                color: root.currentMode === modelData.mode ? "white" : "#888"
                                font.pixelSize: 11
                                font.family: koreanFont.font.family
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.currentMode = modelData.mode
                            }
                        }
                    }
                }
            }

            // 채팅 영역
            ListView {
                id: chatList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 4
                bottomMargin: 8
                topMargin: 8
                leftMargin: 4
                rightMargin: 4

                model: messageModel

                delegate: ChatBubble {
                    width: chatList.width - 8
                    role: model.role
                    content: model.content
                    fontFamily: koreanFont.font.family
                }

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        implicitWidth: 4
                        radius: 2
                        color: "#555"
                    }
                }
            }

            // 입력 영역
            Rectangle {
                Layout.fillWidth: true
                height: 48
                color: "#252525"
                radius: 16

                RowLayout {
                    anchors { fill: parent; leftMargin: 10; rightMargin: 10; topMargin: 6; bottomMargin: 6 }
                    spacing: 6

                    Rectangle {
                        Layout.fillWidth: true
                        height: 32
                        radius: 8
                        color: "#2A2A2A"
                        border.color: inputField.activeFocus ? "#4A90D9" : "#444"
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        TextInput {
                            id: inputField
                            anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                            verticalAlignment: TextInput.AlignVCenter
                            color: "#E0E0E0"
                            font.pixelSize: 13
                            font.family: koreanFont.font.family
                            clip: true

                            Text {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                text: "메시지 입력..."
                                color: "#555"
                                font: inputField.font
                                visible: inputField.text === "" && !inputField.activeFocus
                            }

                            Keys.onReturnPressed: sendMessage()
                        }
                    }

                    Rectangle {
                        width: 32; height: 32
                        radius: 8
                        color: sendBtn.enabled
                               ? (sendBtnHover.containsMouse ? "#357ABD" : "#4A90D9")
                               : "#333"
                        Behavior on color { ColorAnimation { duration: 150 } }

                        Text {
                            id: sendBtn
                            property bool enabled: true
                            anchors.centerIn: parent
                            text: enabled ? "▶" : "…"
                            color: enabled ? "white" : "#666"
                            font.pixelSize: 13
                        }

                        MouseArea {
                            id: sendBtnHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: sendBtn.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: if (sendBtn.enabled) sendMessage()
                        }
                    }
                }
            }
        }
    }

    // ── 메시지 전송 ─────────────────────────────────────────────────────────
    function sendMessage() {
        var text = inputField.text.trim()
        if (text === "") return
        inputField.text = ""
        bridge.sendMessage(text)
    }
}
