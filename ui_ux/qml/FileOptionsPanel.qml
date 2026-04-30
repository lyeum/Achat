import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 파일 옵션 패널 — 파일이름 변경 / 확장자 변경
// 부모 컨테이너 안에 z:10 오버레이로 배치
Item {
    id: fileOptRoot

    property string fontFamily: ""
    property string pathsJson:  "[]"   // browseFilesForOptions() 결과
    // 내부 상태
    property var   _paths:      []
    property int   _mode:       0      // 0=파일이름변경, 1=확장자변경
    property string _renameTo:  ""
    property string _newExt:    ""

    signal closeRequested()
    signal resultReady(string message)

    onPathsJsonChanged: {
        try { _paths = JSON.parse(pathsJson) } catch(e) { _paths = [] }
        _mode = 0
    }

    function _refreshPaths(json) {
        fileOptRoot.pathsJson = json
    }

    // ── 배경 딤 ───────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.45
        MouseArea {
            anchors.fill: parent
            onClicked: fileOptRoot.closeRequested()
        }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panel
        width: Math.min(parent.width - 32, 320)
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

            // 헤더 + 선택 버튼
            RowLayout {
                width: parent.width
                spacing: 8

                Text {
                    text: "파일 변환"
                    font.pixelSize: 14
                    font.bold: true
                    font.family: fileOptRoot.fontFamily
                    color: "#A8D0E0"
                    Layout.fillWidth: false
                }

                Item { Layout.fillWidth: true }

                // 파일 선택 버튼
                Rectangle {
                    width: 72; height: 26; radius: 5
                    color: selFileHov.containsMouse ? "#2A4858" : "#1E3848"
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        anchors.centerIn: parent
                        text: "파일 선택"
                        font.pixelSize: 12
                        font.family: fileOptRoot.fontFamily
                        color: "#7ABAC8"
                    }
                    MouseArea {
                        id: selFileHov
                        anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: fileOptRoot._refreshPaths(bridge.browseFilesForOptions())
                    }
                }

                // 폴더 선택 버튼
                Rectangle {
                    width: 72; height: 26; radius: 5
                    color: selFolderHov.containsMouse ? "#2A4858" : "#1E3848"
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        anchors.centerIn: parent
                        text: "폴더 선택"
                        font.pixelSize: 12
                        font.family: fileOptRoot.fontFamily
                        color: "#7ABAC8"
                    }
                    MouseArea {
                        id: selFolderHov
                        anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: fileOptRoot._refreshPaths(bridge.browseFolderForFileOptions())
                    }
                }
            }

            // 선택된 파일 목록 (최대 3개 표시) — 미선택 시 안내 메시지
            Rectangle {
                width: parent.width
                height: fileOptRoot._paths.length > 0
                    ? Math.min(fileOptRoot._paths.length, 3) * 20 + 8
                    : 28
                color: "#121820"
                radius: 6
                clip: true

                // 미선택 안내
                Text {
                    anchors.centerIn: parent
                    visible: fileOptRoot._paths.length === 0
                    text: "위 버튼으로 파일 또는 폴더를 선택하세요"
                    font.pixelSize: 12
                    font.family: fileOptRoot.fontFamily
                    color: "#3A5060"
                }

                Column {
                    anchors { fill: parent; margins: 4 }
                    spacing: 0
                    visible: fileOptRoot._paths.length > 0
                    Repeater {
                        model: Math.min(fileOptRoot._paths.length, 3)
                        Text {
                            width: parent.width
                            text: {
                                var p = fileOptRoot._paths[index] || ""
                                var name = p.split(/[/\\]/).pop()
                                return (index === 2 && fileOptRoot._paths.length > 3)
                                    ? "... 외 " + (fileOptRoot._paths.length - 2) + "개"
                                    : name
                            }
                            font.pixelSize: 13
                            font.family: fileOptRoot.fontFamily
                            color: "#7090A0"
                            elide: Text.ElideLeft
                        }
                    }
                }
            }

            // 옵션 선택 (라디오)
            Row {
                spacing: 16
                Repeater {
                    model: ["파일이름 변경", "확장자 변경"]
                    Row {
                        spacing: 6
                        Rectangle {
                            width: 16; height: 16
                            radius: 8
                            color: "transparent"
                            border.color: fileOptRoot._mode === index ? "#5A9EA8" : "#3A5060"
                            border.width: 2
                            Rectangle {
                                anchors.centerIn: parent
                                width: 8; height: 8
                                radius: 4
                                color: "#5A9EA8"
                                visible: fileOptRoot._mode === index
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: fileOptRoot._mode = index
                            }
                        }
                        Text {
                            text: modelData
                            font.pixelSize: 14
                            font.family: fileOptRoot.fontFamily
                            color: fileOptRoot._mode === index ? "#A8D0D8" : "#607080"
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: fileOptRoot._mode = parent.parent.model.index
                            }
                        }
                    }
                }
            }

            // ── 파일이름 변경 입력 ─────────────────────────────────────────────
            Column {
                width: parent.width
                spacing: 6
                visible: fileOptRoot._mode === 0

                Text {
                    text: fileOptRoot._paths.length === 1
                        ? "새 파일 이름 (확장자 제외):"
                        : "공통 접두어 (예: photo → photo_001, photo_002...):"
                    font.pixelSize: 13
                    font.family: fileOptRoot.fontFamily
                    color: "#7090A0"
                }
                Rectangle {
                    width: parent.width
                    height: 32
                    radius: 6
                    color: "#121820"
                    border.color: renameInput.activeFocus ? "#5A9EA8" : "#2A3848"
                    border.width: 1
                    TextInput {
                        id: renameInput
                        anchors { fill: parent; margins: 8 }
                        font.pixelSize: 15
                        font.family: fileOptRoot.fontFamily
                        color: "#C8E0E8"
                        onTextChanged: fileOptRoot._renameTo = text
                        Text {
                            anchors.fill: parent
                            text: "새 이름 입력..."
                            font: parent.font
                            color: "#3A5060"
                            visible: parent.text === ""
                        }
                    }
                }
            }

            // ── 확장자 변경 선택 ───────────────────────────────────────────────
            Column {
                width: parent.width
                spacing: 6
                visible: fileOptRoot._mode === 1

                Text {
                    text: "변환할 확장자 선택:"
                    font.pixelSize: 13
                    font.family: fileOptRoot.fontFamily
                    color: "#7090A0"
                }
                Rectangle {
                    width: parent.width
                    height: 120
                    color: "#121820"
                    radius: 6
                    clip: true

                    ScrollView {
                        anchors.fill: parent
                        contentWidth: availableWidth
                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                            contentItem: Rectangle { color: "transparent" }
                            background: Rectangle { color: "transparent" }
                        }
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                        Column {
                            width: parent.width
                            spacing: 0
                            Repeater {
                                model: ["jpg", "png", "webp", "bmp", "tiff", "gif", "mp4", "mp3", "pdf", "txt", "csv", "xlsx"]
                                Rectangle {
                                    width: parent.width
                                    height: 28
                                    color: fileOptRoot._newExt === modelData
                                        ? "#1E3848"
                                        : (extHover.containsMouse ? "#182838" : "transparent")
                                    Row {
                                        anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                                        spacing: 8
                                        Rectangle {
                                            width: 10; height: 10; radius: 5
                                            color: "#5A9EA8"
                                            visible: fileOptRoot._newExt === modelData
                                        }
                                        Text {
                                            text: "." + modelData
                                            font.pixelSize: 14
                                            font.family: fileOptRoot.fontFamily
                                            color: fileOptRoot._newExt === modelData ? "#A8D0D8" : "#607080"
                                        }
                                    }
                                    MouseArea {
                                        id: extHover
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: fileOptRoot._newExt = modelData
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── 버튼 행 ───────────────────────────────────────────────────────
            Row {
                spacing: 8
                layoutDirection: Qt.RightToLeft
                width: parent.width

                // 적용 버튼
                Rectangle {
                    width: 70; height: 30
                    radius: 6
                    color: applyHov.containsMouse ? "#3A7888" : "#2A6070"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        text: "적용"
                        font.pixelSize: 14
                        font.family: fileOptRoot.fontFamily
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: applyHov
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            // renameInput.text를 직접 읽어야 IME preedit 씹힘을 방지한다.
                            // onTextChanged는 조합 중에도 발화되므로 _renameTo 경유 금지.
                            var renameTo = (fileOptRoot._mode === 0) ? renameInput.text.trim() : ""
                            var newExt   = (fileOptRoot._mode === 1) ? fileOptRoot._newExt   : ""
                            if (renameTo === "" && newExt === "") {
                                return  // 아무것도 설정되지 않음
                            }
                            var result = bridge.applyFileOptions(
                                fileOptRoot.pathsJson, renameTo, newExt
                            )
                            fileOptRoot.resultReady(result)
                            fileOptRoot.closeRequested()
                        }
                    }
                }

                // 취소 버튼
                Rectangle {
                    width: 70; height: 30
                    radius: 6
                    color: cancelHov.containsMouse ? "#2A3040" : "#1E2838"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent
                        text: "취소"
                        font.pixelSize: 14
                        font.family: fileOptRoot.fontFamily
                        color: "#8090A0"
                    }
                    MouseArea {
                        id: cancelHov
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: fileOptRoot.closeRequested()
                    }
                }
            }
        }
    }
}
