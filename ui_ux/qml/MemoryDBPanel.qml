import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 기억 DB 관리 패널 — SideMenuPanel "DB 조회 및 관리" 항목으로 열림
// ChromaDB 항목을 카드 형태로 표시하며 추가·수정·삭제를 지원한다.
Item {
    id: dbRoot

    property string fontFamily: ""
    property string dbJson:     "{}"   // bridge.getMemoryDB() 결과

    signal closeRequested()
    signal deleteRequested(string entryId)
    signal addRequested(string content, string metaJson)
    signal updateRequested(string entryId, string newContent, string metaJson)

    // ── 파싱 ─────────────────────────────────────────────────────────────────
    property var _db: {
        try { return JSON.parse(dbRoot.dbJson) }
        catch(e) { return { collection: "", total: 0, sessions: {} } }
    }

    // 카드 목록: 세션 정렬 후 플랫하게 펼침
    property var _entries: {
        var db = _db
        var sessions = db.sessions || {}
        var keys = Object.keys(sessions)
        keys.sort(function(a, b) { return b.localeCompare(a) })
        var list = []
        for (var i = 0; i < keys.length; i++) {
            var arr = sessions[keys[i]]
            for (var j = 0; j < arr.length; j++) {
                list.push(arr[j])
            }
        }
        return list
    }

    // 추가 폼 표시 여부
    property bool _addFormOpen: false

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

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panel
        width: 380
        anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
        color: "#131320"
        border.color: "#2A2A40"
        border.width: 1

        Column {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            spacing: 0

            // ── 헤더 ─────────────────────────────────────────────────────────
            Rectangle {
                width: parent.width; height: 48
                color: "#0E0E1A"
                border.color: "#2A2A40"; border.width: 0

                Text {
                    anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
                    text: "기억 DB 조회 및 관리"
                    color: "#E0E0E0"; font.pixelSize: 13; font.bold: true
                    font.family: dbRoot.fontFamily
                }

                // 항목 수 뱃지
                Rectangle {
                    anchors { right: closeBtnRect.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
                    width: countLabel.implicitWidth + 12; height: 20; radius: 10
                    color: "#2A2A40"
                    Text {
                        id: countLabel
                        anchors.centerIn: parent
                        text: (dbRoot._db.total || 0) + "개"
                        color: "#8080C0"; font.pixelSize: 10
                        font.family: dbRoot.fontFamily
                    }
                }

                Rectangle {
                    id: closeBtnRect
                    width: 24; height: 24; radius: 12
                    anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                    color: closeHov.containsMouse ? "#3A3A50" : "transparent"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text { anchors.centerIn: parent; text: "×"; color: "#B0B0B0"; font.pixelSize: 16 }
                    MouseArea {
                        id: closeHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: dbRoot.closeRequested()
                    }
                }

                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 1; color: "#2A2A40"
                }
            }

            // ── 추가 버튼 행 ─────────────────────────────────────────────────
            Rectangle {
                width: parent.width; height: 40
                color: "transparent"

                Rectangle {
                    anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                    width: addBtnLabel.implicitWidth + 20; height: 26; radius: 5
                    color: addBtnHov.containsMouse ? "#2A3A6A" : "#1E2A50"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        id: addBtnLabel
                        anchors.centerIn: parent
                        text: dbRoot._addFormOpen ? "▲ 폼 닫기" : "+ 항목 추가"
                        color: "#8AB4F8"; font.pixelSize: 11
                        font.family: dbRoot.fontFamily
                    }
                    MouseArea {
                        id: addBtnHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: dbRoot._addFormOpen = !dbRoot._addFormOpen
                    }
                }

                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 1; color: "#1E1E30"
                }
            }
        }

        // ── 추가 폼 ──────────────────────────────────────────────────────────
        Rectangle {
            id: addForm
            anchors { top: parent.top; topMargin: 90; left: parent.left; right: parent.right }
            height: dbRoot._addFormOpen ? addFormColumn.implicitHeight + 20 : 0
            clip: true
            color: "#0C0C1A"
            border.color: "#2A2A40"; border.width: 1
            visible: height > 0

            Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            Column {
                id: addFormColumn
                anchors { top: parent.top; topMargin: 10; left: parent.left; leftMargin: 12; right: parent.right; rightMargin: 12 }
                spacing: 8

                // 내용
                Text {
                    text: "내용"; color: "#8080A0"; font.pixelSize: 10
                    font.family: dbRoot.fontFamily
                }
                Rectangle {
                    width: parent.width; height: 64
                    color: "#181828"; border.color: "#2A2A40"; border.width: 1; radius: 4
                    TextEdit {
                        id: addContent
                        anchors { fill: parent; margins: 6 }
                        color: "#E0E0E0"; font.pixelSize: 11
                        font.family: dbRoot.fontFamily
                        wrapMode: TextEdit.Wrap
                    }
                    // TextEdit에는 placeholderText 없음 — 빈 상태일 때 오버레이 힌트
                    Text {
                        anchors { left: parent.left; top: parent.top; margins: 6 }
                        text: "기억 내용을 입력하세요..."
                        color: "#505070"; font.pixelSize: 11
                        font.family: dbRoot.fontFamily
                        visible: addContent.text.length === 0
                    }
                }

                // 중요도
                Row {
                    spacing: 8
                    Text { text: "중요도"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                    Slider {
                        id: addImportance
                        from: 0.0; to: 1.0; value: 0.5
                        width: 140
                        stepSize: 0.05
                    }
                    Text {
                        text: addImportance.value.toFixed(2)
                        color: "#A0A0C0"; font.pixelSize: 10
                        font.family: dbRoot.fontFamily
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // 태그
                Row {
                    spacing: 8
                    Text { text: "태그"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                    Rectangle {
                        width: 180; height: 24; radius: 4
                        color: "#181828"; border.color: "#2A2A40"; border.width: 1
                        TextInput {
                            id: addTags
                            anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
                            color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                            placeholderText: "쉼표로 구분"
                        }
                    }
                }

                // 위치
                Row {
                    spacing: 8
                    Text { text: "위치"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                    Rectangle {
                        width: 180; height: 24; radius: 4
                        color: "#181828"; border.color: "#2A2A40"; border.width: 1
                        TextInput {
                            id: addLocation
                            anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
                            color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                            placeholderText: "선택 사항"
                        }
                    }
                }

                // 저장 버튼
                Rectangle {
                    width: 70; height: 26; radius: 5
                    color: saveHov.containsMouse ? "#1A5A3A" : "#143A28"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text {
                        anchors.centerIn: parent; text: "저장"
                        color: "#60D090"; font.pixelSize: 11; font.bold: true
                        font.family: dbRoot.fontFamily
                    }
                    MouseArea {
                        id: saveHov; anchors.fill: parent
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var content = addContent.text.trim()
                            if (!content) return
                            var tags = addTags.text.split(",").map(function(s){ return s.trim() }).filter(function(s){ return s.length > 0 })
                            var meta = {
                                importance: addImportance.value,
                                tags: tags,
                                location: addLocation.text.trim(),
                                session_id: "manual"
                            }
                            dbRoot.addRequested(content, JSON.stringify(meta))
                            // 폼 초기화
                            addContent.text = ""
                            addTags.text    = ""
                            addLocation.text = ""
                            addImportance.value = 0.5
                            dbRoot._addFormOpen = false
                        }
                    }
                }

                Item { height: 4 }
            }
        }

        // ── 카드 목록 ─────────────────────────────────────────────────────────
        ListView {
            id: entryList
            anchors {
                top: parent.top; topMargin: dbRoot._addFormOpen ? 90 + addForm.height : 90
                left: parent.left; right: parent.right; bottom: parent.bottom
            }
            clip: true
            spacing: 6
            model: dbRoot._entries

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: card
                width: entryList.width - 16
                x: 8
                radius: 6
                color: "#1A1A2E"
                border.color: "#2A2A44"; border.width: 1

                // 수정 모드 여부
                property bool _editing: false
                height: _editing ? editCol.implicitHeight + 20 : viewCol.implicitHeight + 20

                Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                // ── 조회 모드 ─────────────────────────────────────────────────
                Column {
                    id: viewCol
                    anchors { top: parent.top; topMargin: 10; left: parent.left; leftMargin: 12; right: parent.right; rightMargin: 12 }
                    spacing: 4
                    visible: !card._editing

                    // 내용
                    Text {
                        width: parent.width
                        text: modelData.content
                        color: "#D8D8F0"; font.pixelSize: 11
                        font.family: dbRoot.fontFamily
                        wrapMode: Text.Wrap
                        maximumLineCount: 4
                        elide: Text.ElideRight
                    }

                    // 메타 정보 행
                    Flow {
                        width: parent.width
                        spacing: 6

                        // 중요도
                        Rectangle {
                            width: impLabel.implicitWidth + 10; height: 16; radius: 8
                            color: {
                                var v = modelData.importance || 0
                                return v >= 0.8 ? "#3A2050" : v >= 0.5 ? "#1E2A40" : "#1E2820"
                            }
                            Text {
                                id: impLabel
                                anchors.centerIn: parent
                                text: "★ " + (modelData.importance || 0).toFixed(2)
                                color: {
                                    var v = modelData.importance || 0
                                    return v >= 0.8 ? "#C080FF" : v >= 0.5 ? "#8AB4F8" : "#60D090"
                                }
                                font.pixelSize: 9; font.family: dbRoot.fontFamily
                            }
                        }

                        // 태그
                        Repeater {
                            model: (modelData.tags || "").split(",").filter(function(t){ return t.trim().length > 0 })
                            Rectangle {
                                width: tagTxt.implicitWidth + 10; height: 16; radius: 8; color: "#1E2040"
                                Text { id: tagTxt; anchors.centerIn: parent; text: "#" + modelData.trim(); color: "#7090D0"; font.pixelSize: 9; font.family: dbRoot.fontFamily }
                            }
                        }

                        // 위치
                        Text {
                            text: modelData.location ? "📍 " + modelData.location : ""
                            color: "#7080A0"; font.pixelSize: 9; font.family: dbRoot.fontFamily
                            visible: (modelData.location || "").length > 0
                        }
                    }

                    // 타임스탬프 + 버튼 행 (Row 대신 Item+anchors — Row 안에서 anchor 사용 불가)
                    Item {
                        width: parent.width; height: 24

                        Text {
                            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                            text: (modelData.timestamp || "").substring(0, 16).replace("T", " ")
                            color: "#505070"; font.pixelSize: 9; font.family: dbRoot.fontFamily
                        }

                        // 삭제 버튼
                        Rectangle {
                            id: delBtn
                            width: 28; height: 22; radius: 4
                            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                            color: delBtnHov.containsMouse ? "#4A1A1A" : "transparent"
                            Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "🗑"; font.pixelSize: 11; color: "#A06060" }
                            MouseArea {
                                id: delBtnHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: dbRoot.deleteRequested(modelData.id)
                            }
                        }

                        // 수정 버튼
                        Rectangle {
                            id: editBtn
                            width: 28; height: 22; radius: 4
                            anchors { right: delBtn.left; rightMargin: 2; verticalCenter: parent.verticalCenter }
                            color: editBtnHov.containsMouse ? "#2A3A5A" : "transparent"
                            Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "✏"; font.pixelSize: 11; color: "#7090C0" }
                            MouseArea {
                                id: editBtnHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    editContent.text     = modelData.content
                                    editImportance.value = modelData.importance || 0.5
                                    editTags.text        = modelData.tags || ""
                                    editLocation.text    = modelData.location || ""
                                    card._editing = true
                                }
                            }
                        }
                    }
                }

                // ── 수정 모드 ─────────────────────────────────────────────────
                Column {
                    id: editCol
                    anchors { top: parent.top; topMargin: 10; left: parent.left; leftMargin: 12; right: parent.right; rightMargin: 12 }
                    spacing: 8
                    visible: card._editing

                    // 내용
                    Rectangle {
                        width: parent.width; height: 64
                        color: "#181828"; border.color: "#3A3A60"; border.width: 1; radius: 4
                        TextEdit {
                            id: editContent
                            anchors { fill: parent; margins: 6 }
                            color: "#E0E0E0"; font.pixelSize: 11
                            font.family: dbRoot.fontFamily
                            wrapMode: TextEdit.Wrap
                        }
                    }

                    // 중요도
                    Row {
                        spacing: 8
                        Text { text: "중요도"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                        Slider {
                            id: editImportance
                            from: 0.0; to: 1.0; stepSize: 0.05; width: 120
                        }
                        Text { text: editImportance.value.toFixed(2); color: "#A0A0C0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                    }

                    // 태그
                    Row {
                        spacing: 8
                        Text { text: "태그"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                        Rectangle {
                            width: 160; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                            TextInput { id: editTags; anchors { fill: parent; leftMargin: 6 }; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                        }
                    }

                    // 위치
                    Row {
                        spacing: 8
                        Text { text: "위치"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                        Rectangle {
                            width: 160; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                            TextInput { id: editLocation; anchors { fill: parent; leftMargin: 6 }; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                        }
                    }

                    // 확인 / 취소
                    Row {
                        spacing: 8

                        Rectangle {
                            width: 50; height: 24; radius: 4
                            color: confirmHov.containsMouse ? "#1A5A3A" : "#143A28"
                            Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "저장"; color: "#60D090"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily }
                            MouseArea {
                                id: confirmHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var tags = editTags.text.split(",").map(function(s){ return s.trim() }).filter(function(s){ return s.length > 0 })
                                    var meta = {
                                        importance: editImportance.value,
                                        tags: tags,
                                        location: editLocation.text.trim(),
                                        session_id: "manual"
                                    }
                                    dbRoot.updateRequested(modelData.id, editContent.text.trim(), JSON.stringify(meta))
                                    card._editing = false
                                }
                            }
                        }

                        Rectangle {
                            width: 50; height: 24; radius: 4
                            color: cancelHov.containsMouse ? "#3A1A1A" : "#281414"
                            Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "취소"; color: "#D06060"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                            MouseArea {
                                id: cancelHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: card._editing = false
                            }
                        }
                    }

                    Item { height: 4 }
                }
            }

            // 빈 상태 안내
            Text {
                anchors.centerIn: parent
                visible: dbRoot._entries.length === 0
                text: "저장된 기억이 없습니다."
                color: "#505070"; font.pixelSize: 12
                font.family: dbRoot.fontFamily
            }
        }
    }
}
