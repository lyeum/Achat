import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 파일 검색 결과 패널
// 검색 결과 목록을 보여주고, 파일을 OS 기본 앱으로 열 수 있음
// "열람완료" 버튼을 눌러야 패널이 닫힘 (파일을 닫아도 패널 유지)
Item {
    id: searchRoot

    property string fontFamily:      ""
    property string resultsJson:     "[]"   // searchFiles() 반환값
    property string query:           ""     // 검색어 (표시용)
    property string searchDirectory: ""     // 재검색용 디렉토리

    property var    _results:        []
    property string _error:          ""
    property string _selectedPath:   ""
    property string extFilter:        ""     // "" = 전체, "jpg,png,..." = 이미지 등

    signal closeRequested()

    // 확장자 필터 변경 시 재검색
    onExtFilterChanged: {
        if (searchRoot.query && searchRoot.searchDirectory) {
            var raw = bridge.searchFiles(searchRoot.query, searchRoot.searchDirectory, searchRoot.extFilter)
            searchRoot.resultsJson = raw
        }
    }

    onResultsJsonChanged: {
        try {
            var parsed = JSON.parse(resultsJson)
            if (Array.isArray(parsed)) {
                _results = parsed
                _error = ""
            } else if (parsed.error) {
                _results = []
                _error = parsed.error
            }
        } catch(e) {
            _results = []
            _error = "결과 파싱 오류"
        }
    }

    // ── 배경 딤 ───────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.45
        // 딤 클릭 시 닫지 않음 — 열람완료 버튼으로만 닫힘
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panel
        width: Math.min(parent.width - 32, 420)
        height: Math.min(parent.height - 64, 520)
        anchors.centerIn: parent
        color: "#1A2030"
        radius: 14
        border.color: "#2A3848"
        border.width: 1

        Column {
            id: headerCol
            anchors { left: parent.left; right: parent.right; top: parent.top }
            anchors.margins: 16
            spacing: 10

            // 헤더 행
            Row {
                width: parent.width
                Text {
                    text: "파일 검색 결과"
                    font.pixelSize: 14
                    font.bold: true
                    font.family: searchRoot.fontFamily
                    color: "#A8D0E0"
                }
            }

            // 검색어 + 건수
            Text {
                text: searchRoot._error
                    ? "오류: " + searchRoot._error
                    : (searchRoot.query ? "\"" + searchRoot.query + "\" — " + searchRoot._results.length + "건" : "")
                font.pixelSize: 13
                font.family: searchRoot.fontFamily
                color: searchRoot._error ? "#C05050" : "#5A8090"
                width: parent.width
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }

            // 확장자 필터 칩
            Row {
                spacing: 4
                Repeater {
                    model: [
                        { label: "전체",  ext: "" },
                        { label: "이미지", ext: "jpg,jpeg,png,webp,bmp,tiff,gif" },
                        { label: "문서",  ext: "txt,md,pdf,docx,hwp,hwpx,xlsx,csv" },
                        { label: "코드",  ext: "py,js,ts,java,cpp,c,h,cs,go,rs,sh" },
                    ]
                    Rectangle {
                        width: filterLbl.implicitWidth + 14
                        height: 22; radius: 11
                        color: searchRoot.extFilter === modelData.ext
                            ? "#2A5060" : (filterHov.containsMouse ? "#1E3040" : "#161C28")
                        border.color: searchRoot.extFilter === modelData.ext ? "#5A9EA8" : "transparent"
                        border.width: 1
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            id: filterLbl
                            anchors.centerIn: parent
                            text: modelData.label
                            font.pixelSize: 11
                            font.family: searchRoot.fontFamily
                            color: searchRoot.extFilter === modelData.ext ? "#A8D0D8" : "#506070"
                        }
                        MouseArea {
                            id: filterHov
                            anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: searchRoot.extFilter = modelData.ext
                        }
                    }
                }
            }
        }

        // 결과 목록
        Rectangle {
            id: listArea
            anchors {
                top: headerCol.bottom
                left: parent.left; right: parent.right
                bottom: footerRow.top
                margins: 16
                topMargin: 8
                bottomMargin: 8
            }
            color: "#121820"
            radius: 8
            clip: true

            ListView {
                id: resultList
                anchors.fill: parent
                anchors.margins: 4
                model: searchRoot._results
                spacing: 2
                clip: true

                ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        contentItem: Rectangle { color: "transparent" }
                        background: Rectangle { color: "transparent" }
                    }

                delegate: Rectangle {
                    width: resultList.width
                    height: itemCol.implicitHeight + 12
                    color: searchRoot._selectedPath === modelData.path
                        ? "#1E3848"
                        : (itemHover.containsMouse ? "#182838" : "transparent")
                    radius: 6

                    Column {
                        id: itemCol
                        anchors { left: parent.left; right: openBtn.left; top: parent.top }
                        anchors.margins: 8
                        anchors.rightMargin: 4
                        spacing: 2

                        Text {
                            width: parent.width
                            text: {
                                var parts = modelData.path.split("/")
                                return parts[parts.length - 1]
                            }
                            font.pixelSize: 14
                            font.bold: true
                            font.family: searchRoot.fontFamily
                            color: "#A8D0D8"
                            elide: Text.ElideMiddle
                        }
                        Text {
                            width: parent.width
                            text: modelData.path
                            font.pixelSize: 9
                            font.family: searchRoot.fontFamily
                            color: "#3A5060"
                            elide: Text.ElideLeft
                        }
                        Text {
                            width: parent.width
                            text: modelData.snippet || ""
                            font.pixelSize: 12
                            font.family: searchRoot.fontFamily
                            color: "#607080"
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }
                    }

                    // 열기 버튼
                    Rectangle {
                        id: openBtn
                        width: 44; height: 24
                        anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        radius: 5
                        color: openBtnHov.containsMouse ? "#3A6878" : "#2A5060"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent
                            text: "열기"
                            font.pixelSize: 12
                            font.family: searchRoot.fontFamily
                            color: "#A0D0D8"
                        }
                        MouseArea {
                            id: openBtnHov
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                searchRoot._selectedPath = modelData.path
                                bridge.openFile(modelData.path)
                            }
                        }
                    }

                    MouseArea {
                        id: itemHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: searchRoot._selectedPath = modelData.path
                    }
                }

                // 결과 없음 표시
                Text {
                    anchors.centerIn: parent
                    visible: searchRoot._results.length === 0 && !searchRoot._error
                    text: "검색 결과가 없습니다."
                    font.pixelSize: 14
                    font.family: searchRoot.fontFamily
                    color: "#3A5060"
                }
            }
        }

        // 열람완료 버튼
        Row {
            id: footerRow
            anchors { bottom: parent.bottom; right: parent.right; margins: 16 }
            spacing: 8

            Rectangle {
                width: 80; height: 30
                radius: 6
                color: doneHov.containsMouse ? "#3A7888" : "#2A6070"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text {
                    anchors.centerIn: parent
                    text: "열람완료"
                    font.pixelSize: 14
                    font.family: searchRoot.fontFamily
                    color: "#FFFFFF"
                }
                MouseArea {
                    id: doneHov
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: searchRoot.closeRequested()
                }
            }
        }
    }
}
