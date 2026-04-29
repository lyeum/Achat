import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 캐릭터 변경 패널 — 타이틀바 "변경" 버튼으로 열림
// 오버레이 방식으로 main.qml 위에 z:20으로 띄움
Item {
    id: charSelectRoot

    property string fontFamily: ""
    property string characterListJson: "[]"   // bridge.getCharacterList() 결과

    signal closeRequested()
    signal characterChanged(string charId)    // 선택 확정 시
    signal addRequested()                      // 캐릭터 추가 버튼

    // ── 배경 딤 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.5
        MouseArea {
            anchors.fill: parent
            onClicked: charSelectRoot.closeRequested()
        }
    }

    // ── 모달 박스 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: modal
        width: 280
        anchors {
            top: parent.top
            topMargin: 48        // 타이틀바(38) + 여백(10) 바로 아래
            horizontalCenter: parent.horizontalCenter
        }
        height: Math.min(contentCol.implicitHeight + 16, charSelectRoot.height - 64)
        color: "#1A1A1A"
        radius: 12
        border.color: "#333"
        border.width: 1

        clip: true

        // 헤더
        Rectangle {
            id: modalHeader
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 38
            color: "#242424"
            radius: 12
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }
            Text {
                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                text: "캐릭터 변경"
                color: "#E0E0E0"; font.pixelSize: 15; font.bold: true
                font.family: charSelectRoot.fontFamily
            }
            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                width: 20; height: 20; radius: 10
                color: closeHov.containsMouse ? "#C03030" : "#444"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                MouseArea {
                    id: closeHov; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: charSelectRoot.closeRequested()
                }
            }
        }

        // 스크롤 목록
        ScrollView {
            anchors {
                top: modalHeader.bottom; bottom: parent.bottom
                left: parent.left; right: parent.right
                topMargin: 4; bottomMargin: 4
            }
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical: ScrollBar {
                contentItem: Rectangle { color: "transparent" }
                background:  Rectangle { color: "transparent" }
            }

            Column {
                id: contentCol
                width: modal.width - 16
                x: 8
                spacing: 0

                // ── 현재 캐릭터 목록 ─────────────────────────────────────────
                Repeater {
                    model: {
                        try { return JSON.parse(charSelectRoot.characterListJson) }
                        catch(e) { return [] }
                    }

                    Rectangle {
                        width: contentCol.width
                        height: 36
                        radius: 6
                        color: itemHov.containsMouse ? "#2E2E2E" : "transparent"
                        Behavior on color { ColorAnimation { duration: 100 } }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                            spacing: 8

                            // 캐릭터 아이콘 (있으면 표시)
                            Rectangle {
                                width: 20; height: 20; radius: 10
                                color: "#333"
                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 1
                                    source: Qt.resolvedUrl("../assets/icons/" + modelData.id + "/" + modelData.id + ".png")
                                    fillMode: Image.PreserveAspectCrop
                                    visible: status === Image.Ready
                                }
                                Text {
                                    anchors.centerIn: parent
                                    text: (modelData.name || modelData.id).slice(0, 1)
                                    color: "#999"; font.pixelSize: 12
                                    font.family: charSelectRoot.fontFamily
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.name || modelData.id
                                color: "#D0D0D0"; font.pixelSize: 15
                                font.family: charSelectRoot.fontFamily
                                elide: Text.ElideRight
                            }

                            // 현재 활성 캐릭터 표시
                            Rectangle {
                                visible: bridge && bridge.characterId === modelData.id
                                width: 6; height: 6; radius: 3
                                color: "#4A90D9"
                            }
                        }

                        MouseArea {
                            id: itemHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                charSelectRoot.characterChanged(modelData.id)
                                charSelectRoot.closeRequested()
                            }
                        }
                    }
                }

                // ── 구분선 ───────────────────────────────────────────────────
                Item { width: contentCol.width; height: 6 }
                Rectangle {
                    width: contentCol.width; height: 1
                    color: "#333"
                }
                Item { width: contentCol.width; height: 6 }

                // ── 캐릭터 추가 버튼 ─────────────────────────────────────────
                Rectangle {
                    width: contentCol.width; height: 36
                    radius: 6
                    color: addHov.containsMouse ? "#1E3A5F" : "transparent"
                    Behavior on color { ColorAnimation { duration: 100 } }

                    RowLayout {
                        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                        spacing: 6
                        Text {
                            text: "+"
                            color: "#4A90D9"; font.pixelSize: 16; font.bold: true
                            font.family: charSelectRoot.fontFamily
                        }
                        Text {
                            text: "캐릭터 추가..."
                            color: "#4A90D9"; font.pixelSize: 15
                            font.family: charSelectRoot.fontFamily
                        }
                    }

                    MouseArea {
                        id: addHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: charSelectRoot.addRequested()
                    }
                }

                Item { height: 4; width: 1 }
            }
        }
    }
}
