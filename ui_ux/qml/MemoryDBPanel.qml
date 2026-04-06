import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 기억 DB 뷰어 패널 — 타이틀바 "DB" 버튼으로 열림
// ChromaDB 컬렉션을 세션별로 그룹화해 열람, 유사 검색 미리보기 제공
Item {
    id: dbRoot

    property string fontFamily: ""
    property string dbJson: "{}"          // bridge.getMemoryDB() 결과
    property string searchResultJson: "[]" // bridge.searchMemoryPreview() 결과

    signal closeRequested()
    signal searchRequested(string query)

    // ── 파싱 ─────────────────────────────────────────────────────────────────
    property var _db: {
        try { return JSON.parse(dbRoot.dbJson) }
        catch(e) { return { collection: "", total: 0, sessions: {} } }
    }
    property var _searchResults: {
        try { return JSON.parse(dbRoot.searchResultJson) }
        catch(e) { return [] }
    }

    // 세션 키 목록 (최신순 정렬)
    property var _sessionKeys: {
        var keys = Object.keys(_db.sessions || {})
        keys.sort(function(a, b) { return b.localeCompare(a) })
        return keys
    }

    // 각 세션 펼침 상태 (session_id → bool)
    property var _expanded: ({})

    // ── 배경 딤 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.55
        MouseArea {
            anchors.fill: parent
            onClicked: {
                var p = panel.mapFromItem(dbRoot, mouseX, mouseY)
                if (!panel.contains(p))
                    dbRoot.closeRequested()
            }
        }
    }

    // ── 사이드 패널 (오른쪽에서 슬라이드인) ──────────────────────────────────
    Rectangle {
        id: panel
        width: 320
        anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
        color: "#131320"
        border.color: "#2A2A40"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── 헤더 ─────────────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 44
                color: "#1C1C30"
                border.color: "#2A2A40"
                border.width: 0

                RowLayout {
                    anchors { fill: parent; leftMargin: 14; rightMargin: 10 }
                    spacing: 6

                    Text {
                        text: "기억 DB"
                        color: "#C0C0E0"; font.pixelSize: 13; font.bold: true
                        font.family: dbRoot.fontFamily
                    }
                    Rectangle {
                        width: collLabel.implicitWidth + 12; height: 18; radius: 9
                        color: "#252538"
                        Text {
                            id: collLabel
                            anchors.centerIn: parent
                            text: (_db.collection || "—") + "  " + (_db.total || 0) + "개"
                            color: "#7070A8"; font.pixelSize: 10
                            font.family: dbRoot.fontFamily
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // 닫기
                    Rectangle {
                        width: 20; height: 20; radius: 10
                        color: closeHov.containsMouse ? "#C03030" : "#333348"
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text { anchors.centerIn: parent; text: "✕"; color: "#CCC"; font.pixelSize: 9 }
                        MouseArea {
                            id: closeHov; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: dbRoot.closeRequested()
                        }
                    }
                }

                // 하단 구분선
                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 1; color: "#2A2A40"
                }
            }

            // ── 검색 바 ──────────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 40
                color: "#1A1A2C"

                RowLayout {
                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                    spacing: 6

                    Rectangle {
                        Layout.fillWidth: true
                        height: 26; radius: 6
                        color: "#20203A"
                        border.color: searchField.activeFocus ? "#5A5AE0" : "#333348"
                        border.width: 1
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        TextInput {
                            id: searchField
                            anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                            verticalAlignment: TextInput.AlignVCenter
                            color: "#D0D0F0"; font.pixelSize: 12
                            font.family: dbRoot.fontFamily
                            clip: true

                            Text {
                                anchors.fill: parent; verticalAlignment: Text.AlignVCenter
                                text: "유사 기억 검색..."
                                color: "#505070"; font.pixelSize: 12
                                font.family: dbRoot.fontFamily
                                visible: !searchField.text && !searchField.activeFocus
                            }

                            Keys.onReturnPressed: {
                                if (text.trim() !== "")
                                    dbRoot.searchRequested(text.trim())
                            }
                        }
                    }

                    Rectangle {
                        width: 34; height: 26; radius: 5
                        color: searchBtnHov.containsMouse ? "#4A4ACA" : "#35358A"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text { anchors.centerIn: parent; text: "검색"; color: "#C0C0F8"; font.pixelSize: 11; font.family: dbRoot.fontFamily }
                        MouseArea {
                            id: searchBtnHov; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { if (searchField.text.trim()) dbRoot.searchRequested(searchField.text.trim()) }
                        }
                    }
                }

                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 1; color: "#2A2A40"
                }
            }

            // ── 검색 결과 (있을 때만 표시) ───────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                visible: _searchResults.length > 0
                height: visible ? Math.min(searchResultCol.implicitHeight + 12, 160) : 0
                color: "#161628"
                clip: true

                ScrollView {
                    anchors { fill: parent; topMargin: 6; bottomMargin: 6 }
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Column {
                        id: searchResultCol
                        width: panel.width - 20
                        x: 10
                        spacing: 4

                        Text {
                            text: "검색 결과 (" + _searchResults.length + "개)"
                            color: "#7070A8"; font.pixelSize: 10; font.bold: true
                            font.family: dbRoot.fontFamily
                        }

                        Repeater {
                            model: _searchResults

                            Rectangle {
                                width: searchResultCol.width
                                height: srContent.implicitHeight + 12
                                radius: 5
                                color: "#1E1E36"
                                border.color: "#35356A"
                                border.width: 1

                                Column {
                                    id: srContent
                                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
                                    spacing: 3

                                    RowLayout {
                                        width: parent.width
                                        spacing: 4
                                        Text {
                                            text: "유사도 " + (modelData.similarity * 100).toFixed(0) + "%"
                                            color: modelData.similarity > 0.7 ? "#6ACA6A" : "#CAAA4A"
                                            font.pixelSize: 10; font.family: dbRoot.fontFamily
                                        }
                                        Text {
                                            text: modelData.tags ? "#" + modelData.tags.replace(/,/g, " #") : ""
                                            color: "#7090C0"; font.pixelSize: 10
                                            font.family: dbRoot.fontFamily
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.content
                                        color: "#B0B0D0"; font.pixelSize: 11
                                        font.family: dbRoot.fontFamily
                                        wrapMode: Text.Wrap
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 1; color: "#2A2A40"
                }
            }

            // ── 세션 목록 (스크롤) ────────────────────────────────────────────
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                clip: true

                Column {
                    id: sessionCol
                    width: panel.width
                    spacing: 0

                    // 기억 없음
                    Text {
                        visible: _sessionKeys.length === 0
                        anchors.horizontalCenter: parent.horizontalCenter
                        topPadding: 30
                        text: "저장된 기억이 없습니다."
                        color: "#505070"; font.pixelSize: 12
                        font.family: dbRoot.fontFamily
                    }

                    Repeater {
                        model: _sessionKeys

                        Column {
                            width: panel.width
                            spacing: 0

                            property string sessKey: modelData
                            property var    entries: (_db.sessions && _db.sessions[sessKey]) ? _db.sessions[sessKey] : []
                            property bool   open:    _expanded[sessKey] !== false  // 기본 펼침

                            // 세션 헤더 행
                            Rectangle {
                                width: parent.width; height: 34
                                color: sessHdrHov.containsMouse ? "#1E1E36" : "#181828"
                                Behavior on color { ColorAnimation { duration: 100 } }

                                RowLayout {
                                    anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                                    spacing: 6

                                    Text {
                                        text: parent.parent.parent.open ? "▾" : "▸"
                                        color: "#5A5A90"; font.pixelSize: 11
                                        font.family: dbRoot.fontFamily
                                    }
                                    Text {
                                        text: sessKey.length > 28 ? sessKey.slice(-28) : sessKey
                                        color: "#9090C0"; font.pixelSize: 11; font.bold: true
                                        font.family: dbRoot.fontFamily
                                        Layout.fillWidth: true
                                        elide: Text.ElideLeft
                                    }
                                    Rectangle {
                                        width: cntLbl.implicitWidth + 10; height: 16; radius: 8
                                        color: "#25253A"
                                        Text {
                                            id: cntLbl
                                            anchors.centerIn: parent
                                            text: entries.length + "개"
                                            color: "#6060A0"; font.pixelSize: 10
                                            font.family: dbRoot.fontFamily
                                        }
                                    }
                                }

                                MouseArea {
                                    id: sessHdrHov; anchors.fill: parent
                                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var tmp = Object.assign({}, _expanded)
                                        // open binding: _expanded[sessKey] !== false → false면 접힘, 나머지 펼침
                                        tmp[sessKey] = open ? false : true
                                        _expanded = tmp  // 재할당으로 binding 재평가 유발
                                    }
                                }

                                // 하단 구분선
                                Rectangle {
                                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                                    height: 1; color: "#222238"
                                }
                            }

                            // 세션 내 기억 항목
                            Column {
                                visible: open
                                width: parent.width
                                spacing: 0

                                Repeater {
                                    model: entries

                                    Rectangle {
                                        width: parent.width; height: entryContent.implicitHeight + 14
                                        color: entryHov.containsMouse ? "#181830" : "#121220"
                                        Behavior on color { ColorAnimation { duration: 80 } }

                                        Column {
                                            id: entryContent
                                            anchors {
                                                left: parent.left; right: parent.right
                                                top: parent.top
                                                leftMargin: 22; rightMargin: 10; topMargin: 8
                                            }
                                            spacing: 4

                                            // 메타 행 (importance dot + tags + timestamp)
                                            RowLayout {
                                                width: parent.width
                                                spacing: 4

                                                // importance 색상 점
                                                Rectangle {
                                                    width: 8; height: 8; radius: 4
                                                    color: {
                                                        var imp = modelData.importance || 0
                                                        if (imp >= 0.8) return "#6ACA6A"
                                                        if (imp >= 0.6) return "#CAAA4A"
                                                        return "#6A6A8A"
                                                    }
                                                }

                                                Text {
                                                    text: (modelData.importance * 100).toFixed(0) + "%"
                                                    color: "#505070"; font.pixelSize: 10
                                                    font.family: dbRoot.fontFamily
                                                }

                                                Text {
                                                    text: modelData.tags ? "#" + modelData.tags.replace(/,/g, " #") : ""
                                                    color: "#506890"; font.pixelSize: 10
                                                    font.family: dbRoot.fontFamily
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    text: modelData.timestamp ? modelData.timestamp.slice(0, 10) : ""
                                                    color: "#404060"; font.pixelSize: 10
                                                    font.family: dbRoot.fontFamily
                                                }
                                            }

                                            // 본문
                                            Text {
                                                width: parent.width
                                                text: modelData.content
                                                color: "#A0A0C0"; font.pixelSize: 11
                                                font.family: dbRoot.fontFamily
                                                wrapMode: Text.Wrap
                                                maximumLineCount: 3
                                                elide: Text.ElideRight
                                            }
                                        }

                                        MouseArea {
                                            id: entryHov; anchors.fill: parent
                                            hoverEnabled: true; cursorShape: Qt.ArrowCursor
                                        }

                                        Rectangle {
                                            anchors { bottom: parent.bottom; left: parent.left; right: parent.right; leftMargin: 20 }
                                            height: 1; color: "#1C1C30"
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { height: 12; width: 1 }
                }
            }
        }
    }
}
