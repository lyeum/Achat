import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 캐릭터 초기화 확인 패널 — 설정 > 캐릭터 > "캐릭터 초기화" 메뉴에서 열림
Item {
    id: resetRoot

    property string fontFamily: ""
    property string characterListJson: "[]"   // bridge.getCharacterList() 결과

    signal closeRequested()
    signal resetConfirmed(string charId)       // 확인 버튼 클릭 시

    property string _selectedId: ""

    // ── 배경 딤 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.55
        MouseArea {
            anchors.fill: parent
            onClicked: resetRoot.closeRequested()
        }
    }

    // ── 모달 박스 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: modal
        width: 280
        height: contentCol.implicitHeight + 20
        anchors.centerIn: parent
        color: "#1A1A1A"
        radius: 12
        border.color: "#3A2020"
        border.width: 1

        ColumnLayout {
            id: contentCol
            anchors { top: parent.top; left: parent.left; right: parent.right;
                      topMargin: 16; leftMargin: 16; rightMargin: 16 }
            spacing: 12

            // 경고 아이콘 + 제목
            Text {
                Layout.fillWidth: true
                text: "⚠  캐릭터 초기화"
                color: "#E07070"; font.pixelSize: 15; font.bold: true
                font.family: resetRoot.fontFamily
                horizontalAlignment: Text.AlignHCenter
            }

            // 안내문
            Text {
                Layout.fillWidth: true
                text: "어떤 캐릭터를 지우실건가요?\n선택한 캐릭터의 대화 기록과\n장기 기억이 모두 삭제됩니다."
                color: "#AAA"; font.pixelSize: 14
                font.family: resetRoot.fontFamily
                horizontalAlignment: Text.AlignHCenter
                lineHeight: 1.4
                wrapMode: Text.WordWrap
            }

            // 구분선
            Rectangle { Layout.fillWidth: true; height: 1; color: "#333" }

            // ── 캐릭터 선택 목록 ─────────────────────────────────────────────
            Column {
                id: charList
                Layout.fillWidth: true
                spacing: 2

                Repeater {
                    model: {
                        try { return JSON.parse(resetRoot.characterListJson) }
                        catch(e) { return [] }
                    }

                    Rectangle {
                        id: charRow
                        width: charList.width
                        height: 34
                        radius: 6
                        readonly property bool _selected: resetRoot._selectedId === modelData.id
                        color: _selected ? "#3A1A1A"
                             : rowHov.containsMouse ? "#252525" : "transparent"
                        border.color: _selected ? "#C04040" : "transparent"
                        border.width: 1
                        Behavior on color { ColorAnimation { duration: 100 } }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                            spacing: 8

                            // 라디오 원 (빈 원)
                            Rectangle {
                                width: 14; height: 14; radius: 7
                                color: "transparent"
                                border.color: charRow._selected ? "#C04040" : "#555"
                                border.width: 1
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.name || modelData.id
                                color: charRow._selected ? "#E08080" : "#C0C0C0"
                                font.pixelSize: 15
                                font.family: resetRoot.fontFamily
                                elide: Text.ElideRight
                            }
                        }

                        MouseArea {
                            id: rowHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: resetRoot._selectedId = modelData.id
                        }
                    }
                }
            }

            // 구분선
            Rectangle { Layout.fillWidth: true; height: 1; color: "#333" }

            // ── 버튼 행 ──────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // 취소
                Rectangle {
                    Layout.fillWidth: true; height: 32; radius: 6
                    color: cancelHov.containsMouse ? "#303030" : "#252525"
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        anchors.centerIn: parent; text: "취소"
                        color: "#AAA"; font.pixelSize: 15
                        font.family: resetRoot.fontFamily
                    }
                    MouseArea {
                        id: cancelHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: resetRoot.closeRequested()
                    }
                }

                // 확인
                Rectangle {
                    Layout.fillWidth: true; height: 32; radius: 6
                    color: resetRoot._selectedId === ""
                           ? "#2A2020"
                           : (confirmHov.containsMouse ? "#8B2020" : "#6B2020")
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        anchors.centerIn: parent; text: "초기화"
                        color: resetRoot._selectedId === "" ? "#664444" : "#FFAAAA"
                        font.pixelSize: 15; font.bold: true
                        font.family: resetRoot.fontFamily
                    }
                    MouseArea {
                        id: confirmHov; anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: resetRoot._selectedId !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (resetRoot._selectedId === "") return
                            resetRoot.resetConfirmed(resetRoot._selectedId)
                            resetRoot.closeRequested()
                        }
                    }
                }
            }

            Item { height: 4; width: 1 }
        }
    }
}
