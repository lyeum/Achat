import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Window {
    id: root

    // ── 크기 / 상태 ─────────────────────────────────────────────────────────
    property bool isBubble: false
    property string currentMode: "chat"   // "chat" | "function"

    width:  isBubble ? 72  : 360
    height: isBubble ? 72  : 520
    flags:  Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color:  "transparent"
    visible: true
    title:  "Achat"

    Behavior on width  { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }
    Behavior on height { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }

    // ── hover 투명도 ─────────────────────────────────────────────────────────
    opacity: hoverArea.containsMouse || isBubble ? 1.0 : 0.25
    Behavior on opacity { NumberAnimation { duration: 300 } }

    // ── 드래그 ───────────────────────────────────────────────────────────────
    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton

        property point clickPos

        onPressed: (mouse) => {
            clickPos = Qt.point(mouse.x, mouse.y)
        }
        onPositionChanged: (mouse) => {
            if (pressed) {
                root.x += mouse.x - clickPos.x
                root.y += mouse.y - clickPos.y
            }
        }
        onReleased: {
            var snapped = bridge.snapToEdge(root.x, root.y, root.width, root.height)
            root.x = snapped[0]
            root.y = snapped[1]
        }
        onDoubleClicked: {
            if (root.isBubble) root.isBubble = false
        }
    }

    // ── 브리지 이벤트 수신 ───────────────────────────────────────────────────
    Connections {
        target: bridge

        function onMessageAdded(role, content) {
            messageModel.append({ "role": role, "content": content })
            // 스크롤을 맨 아래로
            Qt.callLater(() => { chatList.positionViewAtEnd() })
        }

        function onStatusChanged(status) {
            sendBtn.enabled = (status === "ready")
            inputField.enabled = (status === "ready")
            if (status === "thinking") {
                messageModel.append({ "role": "assistant", "content": "..." })
            } else {
                // "..." placeholder 제거 (마지막 항목이 placeholder면)
                if (messageModel.count > 0) {
                    var last = messageModel.get(messageModel.count - 1)
                    if (last.content === "...") messageModel.remove(messageModel.count - 1)
                }
            }
        }

        function onCharacterNameChanged(name) {
            charNameLabel.text = name
        }
    }

    // ── 메시지 모델 ──────────────────────────────────────────────────────────
    ListModel { id: messageModel }

    // ── 메인 컨테이너 ────────────────────────────────────────────────────────
    Rectangle {
        id: container
        anchors.fill: parent
        radius: root.isBubble ? width / 2 : 16
        color:  root.isBubble ? "#4A90D9" : "#1E1E1E"
        clip:   true

        Behavior on radius { NumberAnimation { duration: 200 } }
        Behavior on color  { ColorAnimation  { duration: 200 } }

        // ── 버블 모드: 캐릭터 이니셜 ────────────────────────────────────────
        Text {
            anchors.centerIn: parent
            visible: root.isBubble
            text: bridge.characterName.charAt(0).toUpperCase()
            color: "white"
            font.pixelSize: 28
            font.bold: true
        }

        // ── 확장 모드 ────────────────────────────────────────────────────────
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            visible: !root.isBubble

            // 타이틀바
            Rectangle {
                Layout.fillWidth: true
                height: 38
                color: "#2A2A2A"
                radius: 16  // 상단만 둥글게 (container clip으로 하단 잘림)

                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 8 }

                    Text {
                        id: charNameLabel
                        text: bridge.characterName
                        color: "#E0E0E0"
                        font.pixelSize: 13
                        font.bold: true
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
                            onClicked: root.hide()
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
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.currentMode = modelData.mode
                                // TODO Phase 7: 기능 모드 패널 전환
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
                radius: 16   // 하단만 둥글게 (container clip)

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
                            font.family: "Malgun Gothic"
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

    // ── 메시지 전송 함수 ─────────────────────────────────────────────────────
    function sendMessage() {
        var text = inputField.text.trim()
        if (text === "") return
        inputField.text = ""
        bridge.sendMessage(text)
    }
}
