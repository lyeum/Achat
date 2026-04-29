import QtQuick 2.15
import QtQuick.Controls 2.15

// 사이드 내비게이션 패널 — ≡ 버튼으로 열림
// DB / 설정 / 관리 세 섹션을 아코디언 형태로 제공한다.
Item {
    id: sideRoot

    property string fontFamily: ""

    signal closeRequested()
    signal openMemoryDB()
    signal openSettings()
    signal openAdmin()

    // ── 배경 딤 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.45
        MouseArea {
            anchors.fill: parent
            onClicked: {
                // 패널 바깥 클릭 → 닫기
                var p = panel.mapFromItem(sideRoot, mouseX, mouseY)
                if (!panel.contains(p))
                    sideRoot.closeRequested()
            }
        }
    }

    // ── 패널 본체 (오른쪽 슬라이드인) ───────────────────────────────────────
    Rectangle {
        id: panel
        width: 220
        anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
        color: "#131320"
        border.color: "#2A2A40"
        border.width: 1

        // 슬라이드인 애니메이션
        NumberAnimation on anchors.rightMargin {
            from: -220; to: 0
            duration: 180; easing.type: Easing.OutCubic
            running: sideRoot.visible
        }

        Column {
            anchors { top: parent.top; left: parent.left; right: parent.right }

            // ── 헤더 ─────────────────────────────────────────────────────────
            Rectangle {
                width: parent.width; height: 44
                color: "transparent"
                border.color: "#2A2A40"; border.width: 0

                Text {
                    anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
                    text: "메뉴"
                    color: "#E0E0E0"; font.pixelSize: 13; font.bold: true
                    font.family: sideRoot.fontFamily
                }

                // 닫기 버튼
                Rectangle {
                    width: 24; height: 24; radius: 12
                    anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                    color: closeHov.containsMouse ? "#3A3A50" : "transparent"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        text: "×"; color: "#B0B0B0"; font.pixelSize: 16
                    }
                    MouseArea {
                        id: closeHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: sideRoot.closeRequested()
                    }
                }

                // 하단 구분선
                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 1; color: "#2A2A40"
                }
            }

            // ── 섹션 반복 ────────────────────────────────────────────────────
            Repeater {
                id: sectionRepeater
                model: [
                    {
                        label: "DB",
                        items: [{ label: "DB 조회 및 관리", action: "db" }]
                    },
                    {
                        label: "설정",
                        items: [{ label: "설정 열기", action: "settings" }]
                    },
                    {
                        label: "관리",
                        items: [{ label: "관리자 패널", action: "admin" }]
                    },
                ]

                delegate: Column {
                    width: panel.width
                    property bool _open: false

                    // 섹션 헤더 행
                    Rectangle {
                        width: parent.width; height: 40
                        color: secHov.containsMouse ? "#1E1E30" : "transparent"
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
                            text: modelData.label
                            color: "#C8C8DC"; font.pixelSize: 12; font.bold: true
                            font.family: sideRoot.fontFamily
                        }

                        // ▸ / ▾ 토글 아이콘
                        Text {
                            anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                            text: parent.parent._open ? "▾" : "▸"
                            color: "#7070A0"; font.pixelSize: 10
                        }

                        MouseArea {
                            id: secHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: parent.parent._open = !parent.parent._open
                        }

                        Rectangle {
                            anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                            height: 1; color: "#222236"
                        }
                    }

                    // 서브 항목 목록
                    Column {
                        width: parent.width
                        visible: parent._open
                        clip: true

                        Repeater {
                            model: modelData.items
                            delegate: Rectangle {
                                width: panel.width; height: 36
                                color: itemHov.containsMouse ? "#252540" : "transparent"
                                Behavior on color { ColorAnimation { duration: 100 } }

                                Text {
                                    anchors {
                                        left: parent.left; leftMargin: 32
                                        verticalCenter: parent.verticalCenter
                                    }
                                    text: modelData.label
                                    color: "#A0A0C0"; font.pixelSize: 11
                                    font.family: sideRoot.fontFamily
                                }

                                Rectangle {
                                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                                    height: 1; color: "#1C1C2E"
                                }

                                MouseArea {
                                    id: itemHov; anchors.fill: parent
                                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var act = modelData.action
                                        if (act === "db")       sideRoot.openMemoryDB()
                                        else if (act === "settings") sideRoot.openSettings()
                                        else if (act === "admin")    sideRoot.openAdmin()
                                        sideRoot.closeRequested()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
