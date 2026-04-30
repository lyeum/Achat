import QtQuick 2.15
import QtQuick.Controls 2.15

// 이미지 일괄 크롭 패널
Item {
    id: cropRoot

    property string fontFamily: ""
    property string folderPath: ""

    property int    _dirIdx:     0      // 0=위, 1=아래, 2=왼쪽, 3=오른쪽
    property string _previewText: ""

    readonly property var _dirKeys: ["top", "bottom", "left", "right"]

    signal closeRequested()
    signal resultReady(string message)

    // ── 배경 딤 ───────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.45
        MouseArea { anchors.fill: parent; onClicked: cropRoot.closeRequested() }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panel
        width: Math.min(parent.width - 32, 300)
        anchors.centerIn: parent
        height: contentCol.implicitHeight + 32
        color: "#1A2030"
        radius: 14
        border.color: "#2A3848"
        border.width: 1

        Column {
            id: contentCol
            anchors { left: parent.left; right: parent.right; top: parent.top }
            anchors.margins: 16
            spacing: 12

            // 헤더
            Text {
                text: "이미지 일괄 크롭"
                font.pixelSize: 14; font.bold: true
                font.family: cropRoot.fontFamily
                color: "#A8D0E0"
            }

            // 선택된 폴더 경로
            Rectangle {
                width: parent.width; height: 28
                color: "#121820"; radius: 6
                Text {
                    anchors { fill: parent; margins: 6 }
                    text: cropRoot.folderPath || "(경로 없음)"
                    font.pixelSize: 13; font.family: cropRoot.fontFamily
                    color: "#5A8090"; elide: Text.ElideLeft
                    verticalAlignment: Text.AlignVCenter
                }
            }

            // 방향 선택 버튼 4개
            Text {
                text: "크롭 방향:"
                font.pixelSize: 13; font.family: cropRoot.fontFamily
                color: "#7090A0"
            }

            Row {
                spacing: 6
                Repeater {
                    model: ["위", "아래", "왼쪽", "오른쪽"]
                    Rectangle {
                        width: 58; height: 28; radius: 6
                        color: cropRoot._dirIdx === index
                            ? "#2A6070" : (dirHov.containsMouse ? "#1E3040" : "#121820")
                        border.color: cropRoot._dirIdx === index ? "#5A9EA8" : "transparent"
                        border.width: 1
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            font.pixelSize: 13; font.family: cropRoot.fontFamily
                            color: cropRoot._dirIdx === index ? "#FFFFFF" : "#607080"
                        }
                        MouseArea {
                            id: dirHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                cropRoot._dirIdx = index
                                cropRoot._previewText = ""
                            }
                        }
                    }
                }
            }

            // 크기 입력 (width × height)
            Text {
                text: {
                    var dir = cropRoot._dirIdx
                    if (dir === 0 || dir === 1) return "높이 (px) — 폭은 선택:"
                    return "폭 (px) — 높이는 선택:"
                }
                font.pixelSize: 13; font.family: cropRoot.fontFamily
                color: "#7090A0"
            }

            Row {
                spacing: 8

                // Width 입력
                Column {
                    spacing: 4
                    Text {
                        text: "폭"
                        font.pixelSize: 12; font.family: cropRoot.fontFamily
                        color: "#506070"
                    }
                    Rectangle {
                        width: 80; height: 32; radius: 6
                        color: "#121820"
                        border.color: widthInput.activeFocus ? "#5A9EA8" : "#2A3848"
                        border.width: 1
                        TextInput {
                            id: widthInput
                            anchors { fill: parent; margins: 8 }
                            font.pixelSize: 14; font.family: cropRoot.fontFamily
                            color: "#C8E0E8"
                            validator: IntValidator { bottom: 1; top: 99999 }
                            inputMethodHints: Qt.ImhDigitsOnly
                            Text {
                                anchors.fill: parent
                                text: "0 = 원본"
                                font: parent.font; color: "#3A5060"
                                visible: parent.text === ""
                            }
                        }
                    }
                }

                Text {
                    text: "×"
                    font.pixelSize: 18; color: "#506070"
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 8
                }

                // Height 입력
                Column {
                    spacing: 4
                    Text {
                        text: "높이"
                        font.pixelSize: 12; font.family: cropRoot.fontFamily
                        color: "#506070"
                    }
                    Rectangle {
                        width: 80; height: 32; radius: 6
                        color: "#121820"
                        border.color: heightInput.activeFocus ? "#5A9EA8" : "#2A3848"
                        border.width: 1
                        TextInput {
                            id: heightInput
                            anchors { fill: parent; margins: 8 }
                            font.pixelSize: 14; font.family: cropRoot.fontFamily
                            color: "#C8E0E8"
                            validator: IntValidator { bottom: 1; top: 99999 }
                            inputMethodHints: Qt.ImhDigitsOnly
                            Text {
                                anchors.fill: parent
                                text: "0 = 원본"
                                font: parent.font; color: "#3A5060"
                                visible: parent.text === ""
                            }
                        }
                    }
                }
            }

            // 미리보기 결과 (인라인)
            Rectangle {
                width: parent.width; height: 100
                visible: cropRoot._previewText !== ""
                color: "#0E1520"; radius: 6; clip: true
                ScrollView {
                    anchors.fill: parent; anchors.margins: 6
                    contentWidth: availableWidth
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        contentItem: Rectangle { color: "transparent" }
                        background: Rectangle { color: "transparent" }
                    }
                    Text {
                        width: parent.width
                        text: cropRoot._previewText
                        font.pixelSize: 12; font.family: cropRoot.fontFamily
                        color: "#7ABAC8"
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    }
                }
            }

            // ── 버튼 행 ───────────────────────────────────────────────────────
            Row {
                spacing: 6
                layoutDirection: Qt.RightToLeft
                width: parent.width

                // 크롭 실행
                Rectangle {
                    width: 80; height: 30; radius: 6
                    color: cropApplyHov.containsMouse ? "#3A7888" : "#2A6070"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent; text: "크롭 실행"
                        font.pixelSize: 14; font.family: cropRoot.fontFamily; color: "#FFFFFF"
                    }
                    MouseArea {
                        id: cropApplyHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var w = parseInt(widthInput.text)  || 0
                            var h = parseInt(heightInput.text) || 0
                            var result = bridge.applyImageCrop(
                                cropRoot.folderPath,
                                cropRoot._dirKeys[cropRoot._dirIdx],
                                w, h, false
                            )
                            cropRoot.resultReady(result)
                            cropRoot.closeRequested()
                        }
                    }
                }

                // 미리보기
                Rectangle {
                    width: 70; height: 30; radius: 6
                    color: cropPrevHov.containsMouse ? "#2A4858" : "#1E3848"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent; text: "미리보기"
                        font.pixelSize: 14; font.family: cropRoot.fontFamily; color: "#7ABAC8"
                    }
                    MouseArea {
                        id: cropPrevHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var w = parseInt(widthInput.text)  || 0
                            var h = parseInt(heightInput.text) || 0
                            cropRoot._previewText = bridge.applyImageCrop(
                                cropRoot.folderPath,
                                cropRoot._dirKeys[cropRoot._dirIdx],
                                w, h, true
                            )
                        }
                    }
                }

                // 취소
                Rectangle {
                    width: 60; height: 30; radius: 6
                    color: cropCancelHov.containsMouse ? "#2A3040" : "#1E2838"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent; text: "취소"
                        font.pixelSize: 14; font.family: cropRoot.fontFamily; color: "#8090A0"
                    }
                    MouseArea {
                        id: cropCancelHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: cropRoot.closeRequested()
                    }
                }
            }
        }
    }
}
