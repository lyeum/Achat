import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 커스터마이징 편집 패널 — 전체 오버레이 모달
//
// 파츠 타입: base / hair / eye / mouth / cloth
// 감정 효과는 icons/{id}/emotion/ 폴더에서 자동 적용 (사용자 커스텀 불가)
Item {
    id: customRoot

    property string fontFamily:       ""
    property string partsJson:        "{}"   // 현재 parts.json 내용
    property string allPartsListJson: "{}"   // getAllPartsList() 반환값

    signal closeRequested()
    signal saved(string partsJson)

    // ── 내부 편집 상태 ────────────────────────────────────────────────────────
    property var _editParts: ({})

    Component.onCompleted: _resetState()
    onPartsJsonChanged: _resetState()

    function _resetState() {
        try { _editParts = JSON.parse(customRoot.partsJson) } catch(e) { _editParts = {} }
    }

    // ── 딤 배경 (클릭으로 닫기) ──────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.65
        MouseArea {
            anchors.fill: parent
            onClicked: customRoot.closeRequested()
        }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panelRect
        anchors { fill: parent; margins: 10 }
        color: "#1A1A1A"
        radius: 12

        // 패널 영역 내 빈 공간 클릭이 딤 배경까지 전파되지 않도록 이벤트 소비
        MouseArea { anchors.fill: parent; onClicked: {} }

        ColumnLayout {
            anchors { fill: parent; margins: 0 }
            spacing: 0

            // 헤더
            Rectangle {
                Layout.fillWidth: true
                height: 40
                color: "#242424"
                radius: 12
                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 12; color: parent.color
                }
                Text {
                    anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                    text: "캐릭터 커스터마이징"
                    color: "#E0E0E0"; font.pixelSize: 13; font.bold: true
                    font.family: customRoot.fontFamily
                }
                Rectangle {
                    anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                    width: 20; height: 20; radius: 10
                    color: xHover.containsMouse ? "#C03030" : "#444"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                    MouseArea {
                        id: xHover; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: customRoot.closeRequested()
                    }
                }
            }

            // 안내 텍스트
            Text {
                Layout.fillWidth: true
                Layout.topMargin: 8
                Layout.leftMargin: 12
                Layout.rightMargin: 12
                text: "파츠를 선택해 캐릭터를 구성합니다.\n감정 효과는 icons/{캐릭터}/emotion/ 폴더에서 자동 적용됩니다."
                color: "#666"; font.pixelSize: 9; font.family: customRoot.fontFamily
                wrapMode: Text.Wrap
            }

            // 파츠 목록
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: panelRect.width - 20
                    x: 10
                    spacing: 4

                    Item { Layout.preferredHeight: 4 }

                    Repeater {
                        model: [
                            { key: "base",  label: "베이스 (얼굴/몸통)" },
                            { key: "hair",  label: "헤어"              },
                            { key: "eye",   label: "눈"                },
                            { key: "mouth", label: "입"                },
                            { key: "cloth", label: "의상"              },
                        ]

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: modelData.label
                                color: "#4A90D9"; font.pixelSize: 10; font.bold: true
                                font.family: customRoot.fontFamily
                                leftPadding: 2
                            }

                            Item {
                                Layout.fillWidth: true
                                height: 36

                                property var _files: {
                                    try {
                                        var all = JSON.parse(customRoot.allPartsListJson)
                                        return all[modelData.key] || []
                                    } catch(e) { return [] }
                                }
                                property string _key: modelData.key
                                property string _selected: customRoot._editParts[modelData.key] || ""

                                Text {
                                    visible: parent._files.length === 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: 4
                                    text: "파츠 없음"
                                    color: "#555"; font.pixelSize: 10
                                    font.family: customRoot.fontFamily
                                }

                                ListView {
                                    visible: parent._files.length > 0
                                    anchors.fill: parent
                                    orientation: ListView.Horizontal
                                    clip: true
                                    spacing: 4
                                    model: parent._files

                                    property string outerKey:      parent._key
                                    property string outerSelected: parent._selected

                                    delegate: Rectangle {
                                        width: 80; height: 32
                                        radius: 6
                                        color: {
                                            var sel = ListView.view.outerSelected === modelData
                                            return sel ? "#4A90D9"
                                                       : (ph.containsMouse ? "#333" : "#2A2A2A")
                                        }
                                        Behavior on color { ColorAnimation { duration: 100 } }

                                        Text {
                                            anchors { fill: parent; margins: 4 }
                                            text: modelData
                                            color: ListView.view.outerSelected === modelData
                                                   ? "white" : "#CCC"
                                            font.pixelSize: 9
                                            font.family: customRoot.fontFamily
                                            elide: Text.ElideRight
                                            verticalAlignment: Text.AlignVCenter
                                            horizontalAlignment: Text.AlignHCenter
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        }

                                        MouseArea {
                                            id: ph; anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var key = ListView.view.outerKey
                                                var p = Object.assign({}, customRoot._editParts)
                                                if (p[key] === modelData) {
                                                    delete p[key]
                                                } else {
                                                    p[key] = modelData
                                                }
                                                customRoot._editParts = p
                                            }
                                        }
                                    }
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: "#2A2A2A" }
                        }
                    }

                    Item { Layout.preferredHeight: 6 }
                }
            }

            // 하단 저장 / 취소
            Rectangle {
                Layout.fillWidth: true
                height: 44
                color: "#242424"
                radius: 12
                Rectangle {
                    anchors { top: parent.top; left: parent.left; right: parent.right }
                    height: 12; color: parent.color
                }
                RowLayout {
                    anchors { fill: parent; margins: 8 }
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    Rectangle {
                        width: 60; height: 26; radius: 6
                        color: cancelHover.containsMouse ? "#3C3C3C" : "#2A2A2A"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent; text: "취소"
                            color: "#AAA"; font.pixelSize: 11; font.family: customRoot.fontFamily
                        }
                        MouseArea {
                            id: cancelHover; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: customRoot.closeRequested()
                        }
                    }

                    Rectangle {
                        width: 60; height: 26; radius: 6
                        color: saveHover.containsMouse ? "#357ABD" : "#4A90D9"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent; text: "저장"
                            color: "white"; font.pixelSize: 11; font.family: customRoot.fontFamily
                        }
                        MouseArea {
                            id: saveHover; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: customRoot.saved(JSON.stringify(customRoot._editParts))
                        }
                    }
                }
            }
        }
    }
}
