import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 폴더 분류 설정 패널
Item {
    id: classifyRoot

    property string fontFamily:  ""
    property string folderPath:  ""    // browseFolderForClassify() 반환값

    property int    _rule:       0     // 0=종류별, 1=확장자별

    signal closeRequested()
    signal resultReady(string message)

    // ── 배경 딤 ───────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.45
        MouseArea {
            anchors.fill: parent
            onClicked: classifyRoot.closeRequested()
        }
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
                text: "폴더 분류"
                font.pixelSize: 14
                font.bold: true
                font.family: classifyRoot.fontFamily
                color: "#A8D0E0"
            }

            // 선택된 경로
            Rectangle {
                width: parent.width
                height: 28
                color: "#121820"
                radius: 6
                Text {
                    anchors { fill: parent; margins: 6 }
                    text: classifyRoot.folderPath || "(경로 없음)"
                    font.pixelSize: 13
                    font.family: classifyRoot.fontFamily
                    color: "#5A8090"
                    elide: Text.ElideLeft
                    verticalAlignment: Text.AlignVCenter
                }
            }

            // 분류 기준 라디오
            Text {
                text: "분류 기준:"
                font.pixelSize: 13
                font.family: classifyRoot.fontFamily
                color: "#7090A0"
            }

            Column {
                width: parent.width
                spacing: 8
                Repeater {
                    model: [
                        { label: "종류별", desc: "이미지 / 동영상 / 문서 / 코드 / 압축 등으로 분류" },
                        { label: "확장자별", desc: "파일 확장자(.png, .mp4, .pdf ...)별로 폴더 생성" },
                    ]
                    // Row 안에 anchors.fill MouseArea 사용 불가 → Item으로 감쌈
                    Item {
                        width: parent.width
                        height: 36

                        Row {
                            spacing: 8
                            width: parent.width
                            anchors.verticalCenter: parent.verticalCenter
                            Item {
                                width: 16; height: 36
                                Rectangle {
                                    width: 16; height: 16; radius: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: "transparent"
                                    border.color: classifyRoot._rule === index ? "#5A9EA8" : "#3A5060"
                                    border.width: 2
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 8; height: 8; radius: 4
                                        color: "#5A9EA8"
                                        visible: classifyRoot._rule === index
                                    }
                                }
                            }
                            Column {
                                spacing: 2
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    text: modelData.label
                                    font.pixelSize: 14
                                    font.family: classifyRoot.fontFamily
                                    color: classifyRoot._rule === index ? "#A8D0D8" : "#607080"
                                }
                                Text {
                                    text: modelData.desc
                                    font.pixelSize: 12
                                    font.family: classifyRoot.fontFamily
                                    color: "#3A5060"
                                }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: classifyRoot._rule = index
                        }
                    }
                }
            }

            // ── 버튼 행 ───────────────────────────────────────────────────────
            Row {
                spacing: 6
                layoutDirection: Qt.RightToLeft
                width: parent.width

                // 분류 시작 버튼 (dry_run=false)
                Rectangle {
                    width: 80; height: 30; radius: 6
                    color: applyHov.containsMouse ? "#3A7888" : "#2A6070"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        text: "분류 시작"
                        font.pixelSize: 14
                        font.family: classifyRoot.fontFamily
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: applyHov
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var rule = classifyRoot._rule === 0 ? "종류별" : "확장자별"
                            var result = bridge.applyFolderClassify(classifyRoot.folderPath, rule, false)
                            classifyRoot.resultReady(result)
                            classifyRoot.closeRequested()
                        }
                    }
                }

                // 미리보기 버튼 (dry_run=true)
                Rectangle {
                    width: 70; height: 30; radius: 6
                    color: previewHov.containsMouse ? "#2A4858" : "#1E3848"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        text: "미리보기"
                        font.pixelSize: 14
                        font.family: classifyRoot.fontFamily
                        color: "#7ABAC8"
                    }
                    MouseArea {
                        id: previewHov
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var rule = classifyRoot._rule === 0 ? "종류별" : "확장자별"
                            var result = bridge.applyFolderClassify(classifyRoot.folderPath, rule, true)
                            classifyRoot.resultReady(result)
                            // 미리보기는 패널 유지
                        }
                    }
                }

                // 취소 버튼
                Rectangle {
                    width: 60; height: 30; radius: 6
                    color: cancelHov.containsMouse ? "#2A3040" : "#1E2838"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        text: "취소"
                        font.pixelSize: 14
                        font.family: classifyRoot.fontFamily
                        color: "#8090A0"
                    }
                    MouseArea {
                        id: cancelHov
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: classifyRoot.closeRequested()
                    }
                }
            }
        }
    }
}
