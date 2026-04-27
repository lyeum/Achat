import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 기억 DB 관리 패널 — 설정 > DB > "기억 DB 조회 / 편집" 으로 열림
// 탭: 장기 기억 | 세계관 RAG | 프롬프트 가이드
Item {
    id: dbRoot

    property string fontFamily:       ""
    property string dbJson:           "{}"   // bridge.getMemoryDB()
    property string worldDbJson:      "{}"   // bridge.getWorldKnowledgeDB()
    property string promptGuidesJson: "{}"   // bridge.getPromptGuidesDB()

    signal closeRequested()
    signal deleteRequested(string entryId)
    signal addRequested(string content, string metaJson)
    signal updateRequested(string entryId, string newContent, string metaJson)
    signal tabRequested(int tabIndex)     // 탭 전환 시 부모에서 데이터 로드
    signal reindexRequested()             // 세계관 재인덱싱 요청

    // ── 탭 상태 ──────────────────────────────────────────────────────────────
    property int activeTab: 0

    // ── 장기 기억 파싱 ────────────────────────────────────────────────────────
    property var _db: {
        try { return JSON.parse(dbRoot.dbJson) }
        catch(e) { return { collection: "", total: 0, sessions: {} } }
    }

    // 세션별 그룹 목록 (최신 세션 먼저)
    property var _sessionGroups: {
        var sessions = (_db.sessions) || {}
        var keys = Object.keys(sessions)
        keys.sort(function(a, b) { return b.localeCompare(a) })
        var groups = []
        for (var i = 0; i < keys.length; i++) {
            groups.push({ session_id: keys[i], entries: sessions[keys[i]] || [] })
        }
        return groups
    }

    property bool _addFormOpen: false

    // ── 세계관 RAG 파싱 ────────────────────────────────────────────────────────
    property var _worldDb: {
        try { return JSON.parse(dbRoot.worldDbJson) }
        catch(e) { return { total: 0, chunks: [] } }
    }

    // world_id 기준 계층 그룹: [{world_id, sections: [{section, chunks}]}]
    property var _worldGroups: {
        var chunks = (_worldDb.chunks) || []
        var widMap = {}; var widOrder = []
        for (var i = 0; i < chunks.length; i++) {
            var ch = chunks[i]
            var wid = ch.world_id || "(unknown)"
            var sec = ch.section || ""
            if (!widMap[wid]) { widMap[wid] = {}; widOrder.push(wid) }
            if (!widMap[wid][sec]) widMap[wid][sec] = []
            widMap[wid][sec].push(ch)
        }
        var groups = []
        for (var j = 0; j < widOrder.length; j++) {
            var w = widOrder[j]; var secMap = widMap[w]
            var secKeys = Object.keys(secMap)
            var total = 0; var secs = []
            for (var k = 0; k < secKeys.length; k++) {
                secs.push({ section: secKeys[k], chunks: secMap[secKeys[k]] })
                total += secMap[secKeys[k]].length
            }
            groups.push({ world_id: w, sections: secs, total: total })
        }
        return groups
    }

    property bool _worldAddFormOpen: false

    // ── 프롬프트 가이드 파싱 ───────────────────────────────────────────────────
    property var _guidesDb: {
        try { return JSON.parse(dbRoot.promptGuidesJson) }
        catch(e) { return { total: 0, guides: [] } }
    }

    // model_name 기준 그룹
    property var _guideGroups: {
        var guides = (_guidesDb.guides) || []
        var map = {}
        var order = []
        for (var i = 0; i < guides.length; i++) {
            var g = guides[i]
            var mn = g.model_name || "(미지정)"
            if (!map[mn]) { map[mn] = []; order.push(mn) }
            map[mn].push(g)
        }
        var groups = []
        for (var j = 0; j < order.length; j++) {
            groups.push({ model_name: order[j], guides: map[order[j]] })
        }
        return groups
    }

    property bool _guideAddFormOpen: false

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
        width: 400
        anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.right: parent.right
        color: "#131320"
        border.color: "#2A2A40"
        border.width: 1

        // ── 헤더 ─────────────────────────────────────────────────────────────
        Rectangle {
            id: panelHeader
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            height: 46
            color: "#0E0E1A"

            Text {
                anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter
                text: "DB 조회"
                color: "#E0E0E0"; font.pixelSize: 13; font.bold: true
                font.family: dbRoot.fontFamily
            }

            Rectangle {
                id: closeBtnRect
                width: 24; height: 24; radius: 12
                anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                color: closeHov.containsMouse ? "#3A3A50" : "transparent"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "X"; color: "#B0B0B0"; font.pixelSize: 12; font.bold: true }
                MouseArea {
                    id: closeHov; anchors.fill: parent
                    hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: dbRoot.closeRequested()
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                height: 1; color: "#2A2A40"
            }
        }

        // ── 탭 바 ─────────────────────────────────────────────────────────────
        Rectangle {
            id: tabBar
            anchors.top: panelHeader.bottom; anchors.left: parent.left; anchors.right: parent.right
            height: 36
            color: "#0E0E1A"

            Row {
                anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Repeater {
                    model: ["장기 기억", "세계관 RAG", "프롬프트 가이드"]

                    Rectangle {
                        width: tabLabel.implicitWidth + 20
                        height: 26; radius: 5
                        color: dbRoot.activeTab === index
                               ? "#252548"
                               : (tabHov.containsMouse ? "#1A1A30" : "transparent")
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Text {
                            id: tabLabel
                            anchors.centerIn: parent
                            text: modelData
                            color: dbRoot.activeTab === index ? "#A0A0F0" : "#606080"
                            font.pixelSize: 11; font.bold: dbRoot.activeTab === index
                            font.family: dbRoot.fontFamily
                        }

                        Rectangle {
                            visible: dbRoot.activeTab === index
                            anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                            height: 2; color: "#6060C0"; radius: 1
                        }

                        MouseArea {
                            id: tabHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                dbRoot.activeTab = index
                                dbRoot.tabRequested(index)
                            }
                        }
                    }
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                height: 1; color: "#2A2A40"
            }
        }

        // ── 탭 콘텐츠 ─────────────────────────────────────────────────────────
        Item {
            anchors.top: tabBar.bottom; anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right

            // ═══════════════════════════════════════════════════════════════════
            // 탭 0: 장기 기억
            // ═══════════════════════════════════════════════════════════════════
            Item {
                anchors.fill: parent
                visible: dbRoot.activeTab === 0

                // 추가 버튼 행
                Rectangle {
                    id: addBtnBar
                    anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                    height: 40
                    color: "transparent"

                    Rectangle {
                        anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter
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

                    // 항목 수 뱃지
                    Rectangle {
                        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                        width: cntLbl.implicitWidth + 12; height: 20; radius: 10
                        color: "#2A2A40"
                        Text {
                            id: cntLbl
                            anchors.centerIn: parent
                            text: (_db.total || 0) + "개"
                            color: "#8080C0"; font.pixelSize: 10
                            font.family: dbRoot.fontFamily
                        }
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                        height: 1; color: "#1E1E30"
                    }
                }

                // 추가 폼
                Rectangle {
                    id: addForm
                    anchors.top: addBtnBar.bottom; anchors.left: parent.left; anchors.right: parent.right
                    height: dbRoot._addFormOpen ? addFormCol.implicitHeight + 20 : 0
                    clip: true
                    color: "#0C0C1A"
                    border.color: "#2A2A40"; border.width: 1
                    visible: height > 0
                    Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

                    Column {
                        id: addFormCol
                        anchors.top: parent.top; anchors.topMargin: 10; anchors.left: parent.left; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
                        spacing: 8

                        Text { text: "내용"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                        Rectangle {
                            width: parent.width; height: 64
                            color: "#181828"; border.color: "#2A2A40"; border.width: 1; radius: 4
                            TextEdit {
                                id: addContent
                                anchors.fill: parent; anchors.margins: 6
                                color: "#E0E0E0"; font.pixelSize: 11; font.family: dbRoot.fontFamily
                                wrapMode: TextEdit.Wrap
                            }
                            Text {
                                anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 6
                                text: "기억 내용을 입력하세요..."
                                color: "#505070"; font.pixelSize: 11; font.family: dbRoot.fontFamily
                                visible: addContent.text.length === 0
                            }
                        }

                        Row {
                            spacing: 8
                            Text { text: "중요도"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Slider { id: addImportance; from: 0.0; to: 1.0; value: 0.5; width: 140; stepSize: 0.05 }
                            Text { text: addImportance.value.toFixed(2); color: "#A0A0C0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                        }

                        Row {
                            spacing: 8
                            Text { text: "태그"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle {
                                width: 180; height: 24; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                                TextInput { id: addTags; anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors.left: parent.left; anchors.leftMargin: 6; anchors.verticalCenter: parent.verticalCenter; visible: addTags.text.length === 0; text: "쉼표로 구분"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                            }
                        }

                        Row {
                            spacing: 8
                            Text { text: "위치"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle {
                                width: 180; height: 24; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                                TextInput { id: addLocation; anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors.left: parent.left; anchors.leftMargin: 6; anchors.verticalCenter: parent.verticalCenter; visible: addLocation.text.length === 0; text: "선택 사항"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                            }
                        }

                        Rectangle {
                            width: 70; height: 26; radius: 5
                            color: saveHov.containsMouse ? "#1A5A3A" : "#143A28"
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text { anchors.centerIn: parent; text: "저장"; color: "#60D090"; font.pixelSize: 11; font.bold: true; font.family: dbRoot.fontFamily }
                            MouseArea {
                                id: saveHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var c = addContent.text.trim()
                                    if (!c) return
                                    var tags = addTags.text.split(",").map(function(s){ return s.trim() }).filter(function(s){ return s.length > 0 })
                                    var meta = { importance: addImportance.value, tags: tags, location: addLocation.text.trim(), session_id: "manual" }
                                    dbRoot.addRequested(c, JSON.stringify(meta))
                                    addContent.text = ""; addTags.text = ""; addLocation.text = ""; addImportance.value = 0.5
                                    dbRoot._addFormOpen = false
                                }
                            }
                        }

                        Item { height: 4 }
                    }
                }

                // 세션 그룹화 카드 목록
                ScrollView {
                    id: memScrollView
                    anchors.top: addForm.bottom
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Column {
                        id: memCol
                        width: panel.width - 16
                        x: 8
                        spacing: 0

                        // 빈 상태
                        Text {
                            visible: dbRoot._sessionGroups.length === 0
                            text: "저장된 기억이 없습니다."
                            color: "#505070"; font.pixelSize: 12; font.family: dbRoot.fontFamily
                            topPadding: 20; leftPadding: 12
                        }

                        Repeater {
                            model: dbRoot._sessionGroups
                            delegate: Column {
                                id: sessionGroup
                                width: memCol.width
                                spacing: 0
                                property bool _open: true

                                // 세션 헤더
                                Rectangle {
                                    width: parent.width; height: 28
                                    color: sgHov.containsMouse ? "#1A1A2E" : "#131326"
                                    Behavior on color { ColorAnimation { duration: 100 } }

                                    Text {
                                        anchors.left: parent.left; anchors.leftMargin: 4; anchors.verticalCenter: parent.verticalCenter
                                        text: sessionGroup._open ? "▾" : "▸"
                                        color: "#6060A0"; font.pixelSize: 9
                                    }
                                    Text {
                                        anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.session_id
                                        color: "#7070A0"; font.pixelSize: 10; font.bold: true
                                        font.family: dbRoot.fontFamily
                                    }
                                    Rectangle {
                                        anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                                        width: sgCntLbl.implicitWidth + 10; height: 16; radius: 8; color: "#252540"
                                        Text { id: sgCntLbl; anchors.centerIn: parent; text: modelData.entries.length + "개"; color: "#6060A0"; font.pixelSize: 9; font.family: dbRoot.fontFamily }
                                    }
                                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: "#1E1E34" }
                                    MouseArea { id: sgHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: sessionGroup._open = !sessionGroup._open }
                                }

                                // 카드 목록 (펼침)
                                Item {
                                    width: parent.width
                                    height: sessionGroup._open ? entriesCol.implicitHeight : 0
                                    clip: true
                                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                                    Column {
                                        id: entriesCol
                                        width: parent.width
                                        spacing: 6
                                        topPadding: 4; bottomPadding: 4

                                        Repeater {
                                            model: modelData.entries
                                            delegate: Rectangle {
                                                id: card
                                                width: entriesCol.width - 4
                                                x: 2
                                                radius: 6
                                                color: "#1A1A2E"
                                                border.color: "#2A2A44"; border.width: 1
                                                property bool _editing: false
                                                height: _editing ? editCol.implicitHeight + 20 : viewCol.implicitHeight + 20
                                                Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                                                // 조회 모드
                                                Column {
                                                    id: viewCol
                                                    anchors.top: parent.top; anchors.topMargin: 10; anchors.left: parent.left; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
                                                    spacing: 4
                                                    visible: !card._editing

                                                    Text {
                                                        width: parent.width
                                                        text: modelData.content
                                                        color: "#D8D8F0"; font.pixelSize: 11; font.family: dbRoot.fontFamily
                                                        wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight
                                                    }

                                                    Flow {
                                                        width: parent.width
                                                        spacing: 6

                                                        Rectangle {
                                                            width: impLbl.implicitWidth + 10
                                                            height: 16
                                                            radius: 8
                                                            color: {
                                                                var v = modelData.importance || 0
                                                                return v >= 0.8 ? "#3A2050" : v >= 0.5 ? "#1E2A40" : "#1E2820"
                                                            }
                                                            Text {
                                                                id: impLbl
                                                                anchors.centerIn: parent
                                                                text: "중요도 " + (modelData.importance || 0).toFixed(2)
                                                                color: {
                                                                    var v = modelData.importance || 0
                                                                    return v >= 0.8 ? "#C080FF" : v >= 0.5 ? "#8AB4F8" : "#60D090"
                                                                }
                                                                font.pixelSize: 9
                                                                font.family: dbRoot.fontFamily
                                                            }
                                                        }

                                                        Repeater {
                                                            model: (modelData.tags || "").split(",").filter(function(t){ return t.trim().length > 0 })
                                                            Rectangle {
                                                                width: tagTxt.implicitWidth + 10
                                                                height: 16
                                                                radius: 8
                                                                color: "#1E2040"
                                                                Text {
                                                                    id: tagTxt
                                                                    anchors.centerIn: parent
                                                                    text: "#" + modelData.trim()
                                                                    color: "#7090D0"
                                                                    font.pixelSize: 9
                                                                    font.family: dbRoot.fontFamily
                                                                }
                                                            }
                                                        }
                                                    }

                                                    Item {
                                                        width: parent.width; height: 24
                                                        Text { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: (modelData.timestamp || "").substring(0, 16).replace("T", " "); color: "#505070"; font.pixelSize: 9; font.family: dbRoot.fontFamily }
                                                        Rectangle {
                                                            id: delBtn; width: 30; height: 22; radius: 4
                                                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                                            color: delHov.containsMouse ? "#4A1A1A" : "transparent"
                                                            Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "삭제"; font.pixelSize: 9; color: "#A06060"; font.bold: true }
                                                            MouseArea { id: delHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: dbRoot.deleteRequested(modelData.id) }
                                                        }
                                                        Rectangle {
                                                            width: 30; height: 22; radius: 4
                                                            anchors.right: delBtn.left; anchors.rightMargin: 2; anchors.verticalCenter: parent.verticalCenter
                                                            color: editHov.containsMouse ? "#2A3A5A" : "transparent"
                                                            Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "수정"; font.pixelSize: 9; color: "#7090C0"; font.bold: true }
                                                            MouseArea {
                                                                id: editHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    editContent.text = modelData.content
                                                                    editImportance.value = modelData.importance || 0.5
                                                                    editTags.text = modelData.tags || ""
                                                                    editLocation.text = modelData.location || ""
                                                                    card._editing = true
                                                                }
                                                            }
                                                        }
                                                    }
                                                }

                                                // 수정 모드
                                                Column {
                                                    id: editCol
                                                    anchors.top: parent.top; anchors.topMargin: 10; anchors.left: parent.left; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
                                                    spacing: 8; visible: card._editing

                                                    Rectangle {
                                                        width: parent.width; height: 100; color: "#181828"; border.color: "#3A3A60"; border.width: 1; radius: 4; clip: true
                                                        Flickable {
                                                            anchors.fill: parent; anchors.margins: 6
                                                            contentWidth: width; contentHeight: editContent.implicitHeight
                                                            clip: true; flickableDirection: Flickable.VerticalFlick
                                                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                                                            TextEdit { id: editContent; width: parent.width; color: "#E0E0E0"; font.pixelSize: 11; font.family: dbRoot.fontFamily; wrapMode: TextEdit.Wrap; selectByMouse: true }
                                                        }
                                                    }
                                                    Row {
                                                        spacing: 8
                                                        Text { text: "중요도"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                                                        Slider { id: editImportance; from: 0.0; to: 1.0; stepSize: 0.05; width: 120 }
                                                        Text { text: editImportance.value.toFixed(2); color: "#A0A0C0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                                                    }
                                                    Row {
                                                        spacing: 8
                                                        Text { text: "태그"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                                                        Rectangle {
                                                            width: 160; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                                                            TextInput { id: editTags; anchors.fill: parent; anchors.leftMargin: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                                        }
                                                    }
                                                    Row {
                                                        spacing: 8
                                                        Text { text: "위치"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                                                        Rectangle {
                                                            width: 160; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                                                            TextInput { id: editLocation; anchors.fill: parent; anchors.leftMargin: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                                        }
                                                    }
                                                    Row {
                                                        spacing: 8
                                                        Rectangle {
                                                            width: 50; height: 24; radius: 4; color: confHov.containsMouse ? "#1A5A3A" : "#143A28"; Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "저장"; color: "#60D090"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily }
                                                            MouseArea {
                                                                id: confHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    var tags = editTags.text.split(",").map(function(s){ return s.trim() }).filter(function(s){ return s.length > 0 })
                                                                    var meta = { importance: editImportance.value, tags: tags, location: editLocation.text.trim(), session_id: "manual" }
                                                                    dbRoot.updateRequested(modelData.id, editContent.text.trim(), JSON.stringify(meta))
                                                                    card._editing = false
                                                                }
                                                            }
                                                        }
                                                        Rectangle {
                                                            width: 50; height: 24; radius: 4; color: cancHov.containsMouse ? "#3A1A1A" : "#281414"; Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "취소"; color: "#D06060"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                                            MouseArea { id: cancHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: card._editing = false }
                                                        }
                                                    }
                                                    Item { height: 4 }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Item { height: 8 }
                    }
                }
            }

            // ═══════════════════════════════════════════════════════════════════
            // 탭 1: 세계관 RAG
            // ═══════════════════════════════════════════════════════════════════
            Item {
                anchors.fill: parent
                visible: dbRoot.activeTab === 1

                // 상단 버튼 바
                Rectangle {
                    id: worldTopBar
                    anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                    height: 40; color: "transparent"

                    Row {
                        anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter
                        spacing: 6

                        Rectangle {
                            width: wAddLbl.implicitWidth + 20; height: 26; radius: 5
                            color: wAddHov.containsMouse ? "#2A3A6A" : "#1E2A50"
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text { id: wAddLbl; anchors.centerIn: parent; text: dbRoot._worldAddFormOpen ? "▲ 폼 닫기" : "+ 항목 추가"; color: "#8AB4F8"; font.pixelSize: 11; font.family: dbRoot.fontFamily }
                            MouseArea { id: wAddHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: dbRoot._worldAddFormOpen = !dbRoot._worldAddFormOpen }
                        }

                        Rectangle {
                            width: reindexLbl.implicitWidth + 20; height: 26; radius: 5
                            color: reindexHov.containsMouse ? "#2A3A2A" : "#1A2A1A"
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Text { id: reindexLbl; anchors.centerIn: parent; text: "재인덱싱"; color: "#60A860"; font.pixelSize: 11; font.family: dbRoot.fontFamily }
                            MouseArea { id: reindexHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: dbRoot.reindexRequested() }
                        }
                    }

                    Rectangle {
                        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                        width: wCntLbl.implicitWidth + 12; height: 20; radius: 10; color: "#2A2A40"
                        Text { id: wCntLbl; anchors.centerIn: parent; text: (_worldDb.total || 0) + "개"; color: "#8080C0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                    }
                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: "#1E1E30" }
                }

                // 추가 폼
                Rectangle {
                    id: worldAddForm
                    anchors.top: worldTopBar.bottom; anchors.left: parent.left; anchors.right: parent.right
                    height: dbRoot._worldAddFormOpen ? worldAddFormCol.implicitHeight + 20 : 0
                    clip: true; color: "#0C0C1A"; border.color: "#2A2A40"; border.width: 1; visible: height > 0
                    Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

                    Column {
                        id: worldAddFormCol
                        anchors.top: parent.top; anchors.topMargin: 10
                        anchors.left: parent.left; anchors.leftMargin: 12
                        anchors.right: parent.right; anchors.rightMargin: 12
                        spacing: 6

                        Row {
                            spacing: 8
                            Text { text: "world_id"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle { width: 120; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1; clip: true
                                TextInput { id: wAddWorldId; anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 4; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 6 }
                                    text: "ex) seaside_world"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                    visible: wAddWorldId.text.length === 0 && !wAddWorldId.activeFocus }
                            }
                            Text { text: "section"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle { width: 80; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1; clip: true
                                TextInput { id: wAddSection; anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 4; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 6 }
                                    text: "place / story"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                    visible: wAddSection.text.length === 0 && !wAddSection.activeFocus }
                            }
                        }
                        Row {
                            spacing: 8
                            Text { text: "제목"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle { width: 220; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1; clip: true
                                TextInput { id: wAddTitle; anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 4; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 6 }
                                    text: "ex) 등대지기 전설"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                    visible: wAddTitle.text.length === 0 && !wAddTitle.activeFocus }
                            }
                        }
                        Row {
                            spacing: 8
                            Text { text: "트리거(story)"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle { width: 190; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1; clip: true
                                TextInput { id: wAddTrigger; anchors.fill: parent; anchors.leftMargin: 6; anchors.rightMargin: 4; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 6 }
                                    text: "ex) 등대, 전설, 노인"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                    visible: wAddTrigger.text.length === 0 && !wAddTrigger.activeFocus }
                            }
                        }
                        Text { text: "내용"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                        Rectangle {
                            width: parent.width; height: 60; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                            TextEdit { id: wAddContent; anchors.fill: parent; anchors.margins: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; wrapMode: TextEdit.Wrap }
                            Text {
                                anchors { left: parent.left; top: parent.top; leftMargin: 6; topMargin: 6 }
                                text: "이 장소나 사건에 대한 설명을 입력하세요."
                                color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                visible: wAddContent.text.length === 0 && !wAddContent.activeFocus
                            }
                        }
                        Rectangle {
                            width: 60; height: 24; radius: 4; color: wSaveHov.containsMouse ? "#1A5A3A" : "#143A28"; Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "저장"; color: "#60D090"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily }
                            MouseArea {
                                id: wSaveHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var title = wAddTitle.text.trim()
                                    var cnt   = wAddContent.text.trim()
                                    if (!title || !cnt) return
                                    bridge.addWorldKnowledge(wAddWorldId.text.trim(), wAddSection.text.trim(), title, cnt, wAddTrigger.text.trim())
                                    bridge.reindexWorldKnowledge()
                                    dbRoot.worldDbJson = bridge.getWorldKnowledgeDB()
                                    wAddTitle.text = ""; wAddContent.text = ""; wAddTrigger.text = ""
                                    dbRoot._worldAddFormOpen = false
                                }
                            }
                        }
                        Item { height: 4 }
                    }
                }

                ScrollView {
                    anchors.top: worldAddForm.bottom; anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                    clip: true; ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Column {
                        id: worldChunkCol
                        width: panel.width - 16; x: 8; spacing: 0

                        Text {
                            visible: dbRoot._worldGroups.length === 0
                            text: "인덱싱된 세계관 데이터가 없습니다.\n'재인덱싱' 버튼을 눌러 로드하세요."
                            color: "#505070"; font.pixelSize: 12; font.family: dbRoot.fontFamily
                            topPadding: 20; leftPadding: 12; wrapMode: Text.Wrap
                        }

                        // 1단계: world_id
                        Repeater {
                            model: dbRoot._worldGroups
                            delegate: Column {
                                id: wWorldGroup
                                width: worldChunkCol.width; spacing: 0
                                property bool _open: false
                                property var _worldData: modelData

                                // world_id 헤더
                                Rectangle {
                                    width: parent.width; height: 30
                                    color: wWorldHov.containsMouse ? "#1C1C32" : "#131326"
                                    Behavior on color { ColorAnimation { duration: 100 } }

                                    Text { anchors.left: parent.left; anchors.leftMargin: 4; anchors.verticalCenter: parent.verticalCenter; text: wWorldGroup._open ? "▾" : "▸"; color: "#5050A0"; font.pixelSize: 10 }
                                    Text { anchors.left: parent.left; anchors.leftMargin: 18; anchors.verticalCenter: parent.verticalCenter; anchors.right: wWorldBadge.left; anchors.rightMargin: 4
                                           text: _worldData.world_id; color: "#9090D0"; font.pixelSize: 11; font.bold: true; font.family: dbRoot.fontFamily; elide: Text.ElideRight }
                                    Rectangle {
                                        id: wWorldBadge
                                        anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                                        width: wWorldBadgeLbl.implicitWidth + 10; height: 16; radius: 8; color: "#252540"
                                        Text { id: wWorldBadgeLbl; anchors.centerIn: parent; text: _worldData.total + "개"; color: "#6060A0"; font.pixelSize: 9; font.family: dbRoot.fontFamily }
                                    }
                                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: "#1E1E34" }
                                    MouseArea { id: wWorldHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: wWorldGroup._open = !wWorldGroup._open }
                                }

                                // 2단계: section 목록
                                Item {
                                    width: parent.width
                                    height: wWorldGroup._open ? wSecCol.implicitHeight : 0
                                    clip: true
                                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                                    Column {
                                        id: wSecCol; width: parent.width; spacing: 0

                                        Repeater {
                                            model: _worldData.sections
                                            delegate: Column {
                                                id: wSecGroup
                                                width: wSecCol.width; spacing: 0
                                                property bool _open: false
                                                property var _secData: modelData

                                                // section 헤더
                                                Rectangle {
                                                    width: parent.width; height: 26
                                                    color: wSecHov.containsMouse ? "#18182C" : "#111122"
                                                    Behavior on color { ColorAnimation { duration: 100 } }

                                                    Text { anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: wSecGroup._open ? "▾" : "▸"; color: "#505090"; font.pixelSize: 9 }
                                                    Text { anchors.left: parent.left; anchors.leftMargin: 28; anchors.verticalCenter: parent.verticalCenter; anchors.right: wSecBadge.left; anchors.rightMargin: 4
                                                           text: _secData.section; color: "#7070A8"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily; elide: Text.ElideRight }
                                                    Rectangle {
                                                        id: wSecBadge
                                                        anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                                                        width: wSecBadgeLbl.implicitWidth + 8; height: 14; radius: 7; color: "#1E1E38"
                                                        Text { id: wSecBadgeLbl; anchors.centerIn: parent; text: _secData.chunks.length + "개"; color: "#505080"; font.pixelSize: 9; font.family: dbRoot.fontFamily }
                                                    }
                                                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: "#181830" }
                                                    MouseArea { id: wSecHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: wSecGroup._open = !wSecGroup._open }
                                                }

                                                // 3단계: 청크 카드
                                                Item {
                                                    width: parent.width
                                                    height: wSecGroup._open ? wgEntries.implicitHeight : 0
                                                    clip: true
                                                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                                                    Column {
                                                        id: wgEntries; width: parent.width; spacing: 4; topPadding: 4; bottomPadding: 4; leftPadding: 12

                                                        Repeater {
                                                            model: _secData.chunks
                                                            delegate: Rectangle {
                                                                id: wCard
                                                                width: wgEntries.width - 16; radius: 4; color: "#151523"; border.color: "#252540"; border.width: 1
                                                                property bool _editing: false
                                                                height: _editing ? wEditCol.implicitHeight + 16 : wViewCol.implicitHeight + 16
                                                                Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                                                                Column {
                                                                    id: wViewCol
                                                                    anchors.top: parent.top; anchors.topMargin: 8
                                                                    anchors.left: parent.left; anchors.leftMargin: 10
                                                                    anchors.right: parent.right; anchors.rightMargin: 10
                                                                    spacing: 4; visible: !wCard._editing

                                                                    Text {
                                                                        width: parent.width
                                                                        text: modelData.item_title || "-"
                                                                        color: "#9090C0"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily
                                                                    }
                                                                    Text {
                                                                        width: parent.width
                                                                        text: modelData.content
                                                                        color: "#C0C0D8"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                                                        wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight
                                                                    }
                                                                    Item {
                                                                        width: parent.width; height: 22
                                                                        Rectangle {
                                                                            id: wDelBtn; width: 30; height: 20; radius: 4; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                                                            color: wDelHov.containsMouse ? "#4A1A1A" : "transparent"; Behavior on color { ColorAnimation { duration: 100 } }
                                                                            Text { anchors.centerIn: parent; text: "삭제"; font.pixelSize: 9; color: "#A06060"; font.bold: true }
                                                                            MouseArea { id: wDelHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                                onClicked: { bridge.deleteWorldKnowledge(modelData.id); dbRoot.worldDbJson = bridge.getWorldKnowledgeDB() }
                                                                            }
                                                                        }
                                                                        Rectangle {
                                                                            width: 30; height: 20; radius: 4; anchors.right: wDelBtn.left; anchors.rightMargin: 2; anchors.verticalCenter: parent.verticalCenter
                                                                            color: wEditHov.containsMouse ? "#2A3A5A" : "transparent"; Behavior on color { ColorAnimation { duration: 100 } }
                                                                            Text { anchors.centerIn: parent; text: "수정"; font.pixelSize: 9; color: "#7090C0"; font.bold: true }
                                                                            MouseArea { id: wEditHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                                onClicked: { wEditArea.text = modelData.content; wCard._editing = true }
                                                                            }
                                                                        }
                                                                    }
                                                                }

                                                                Column {
                                                                    id: wEditCol
                                                                    anchors.top: parent.top; anchors.topMargin: 8
                                                                    anchors.left: parent.left; anchors.leftMargin: 10
                                                                    anchors.right: parent.right; anchors.rightMargin: 10
                                                                    spacing: 6; visible: wCard._editing

                                                                    // 스크롤 가능한 텍스트 편집 영역
                                                                    Rectangle {
                                                                        width: parent.width; height: 100; radius: 4; color: "#181828"; border.color: "#3A3A60"; border.width: 1; clip: true
                                                                        Flickable {
                                                                            anchors.fill: parent; anchors.margins: 6
                                                                            contentWidth: width; contentHeight: wEditArea.implicitHeight
                                                                            clip: true; flickableDirection: Flickable.VerticalFlick
                                                                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                                                                            TextEdit {
                                                                                id: wEditArea; width: parent.width
                                                                                color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                                                                wrapMode: TextEdit.Wrap; selectByMouse: true
                                                                            }
                                                                        }
                                                                    }
                                                                    Row {
                                                                        spacing: 6
                                                                        Rectangle {
                                                                            width: 50; height: 22; radius: 4; color: wConfHov.containsMouse ? "#1A5A3A" : "#143A28"; Behavior on color { ColorAnimation { duration: 100 } }
                                                                            Text { anchors.centerIn: parent; text: "저장"; color: "#60D090"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily }
                                                                            MouseArea { id: wConfHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                                onClicked: {
                                                                                    bridge.updateWorldKnowledge(modelData.id, wEditArea.text.trim())
                                                                                    dbRoot.worldDbJson = bridge.getWorldKnowledgeDB()
                                                                                    wCard._editing = false
                                                                                }
                                                                            }
                                                                        }
                                                                        Rectangle {
                                                                            width: 50; height: 22; radius: 4; color: wCancHov.containsMouse ? "#3A1A1A" : "#281414"; Behavior on color { ColorAnimation { duration: 100 } }
                                                                            Text { anchors.centerIn: parent; text: "취소"; color: "#D06060"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                                                            MouseArea { id: wCancHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: wCard._editing = false }
                                                                        }
                                                                    }
                                                                    Item { height: 2 }
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
                        }

                        Item { height: 8 }
                    }
                }
            }

            // ═══════════════════════════════════════════════════════════════════
            // 탭 2: 프롬프트 가이드 CRUD
            // ═══════════════════════════════════════════════════════════════════
            Item {
                anchors.fill: parent
                visible: dbRoot.activeTab === 2

                // 상단 버튼 바
                Rectangle {
                    id: guidesTopBar
                    anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                    height: 40; color: "transparent"

                    Rectangle {
                        anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter
                        width: gAddLbl.implicitWidth + 20; height: 26; radius: 5
                        color: gAddHov.containsMouse ? "#2A3A6A" : "#1E2A50"
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text { id: gAddLbl; anchors.centerIn: parent; text: dbRoot._guideAddFormOpen ? "▲ 폼 닫기" : "+ 항목 추가"; color: "#8AB4F8"; font.pixelSize: 11; font.family: dbRoot.fontFamily }
                        MouseArea { id: gAddHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: dbRoot._guideAddFormOpen = !dbRoot._guideAddFormOpen }
                    }

                    Rectangle {
                        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                        width: gCntLbl.implicitWidth + 12; height: 20; radius: 10; color: "#2A2A40"
                        Text { id: gCntLbl; anchors.centerIn: parent; text: (_guidesDb.total || 0) + "개"; color: "#8080C0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                    }
                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: "#1E1E30" }
                }

                // 추가 폼
                Rectangle {
                    id: guideAddForm
                    anchors.top: guidesTopBar.bottom; anchors.left: parent.left; anchors.right: parent.right
                    height: dbRoot._guideAddFormOpen ? guideAddFormCol.implicitHeight + 20 : 0
                    clip: true; color: "#0C0C1A"; border.color: "#2A2A40"; border.width: 1; visible: height > 0
                    Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

                    Column {
                        id: guideAddFormCol
                        anchors.top: parent.top; anchors.topMargin: 10
                        anchors.left: parent.left; anchors.leftMargin: 12
                        anchors.right: parent.right; anchors.rightMargin: 12
                        spacing: 6

                        Row {
                            spacing: 8
                            Text { text: "모델"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle { width: 140; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                                TextInput { id: gAddModel; anchors.fill: parent; anchors.leftMargin: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors.left: parent.left; anchors.leftMargin: 6; anchors.verticalCenter: parent.verticalCenter; visible: gAddModel.text.length === 0; text: "model_name"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                            }
                        }
                        Row {
                            spacing: 8
                            Text { text: "캐릭터"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle { width: 140; height: 22; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                                TextInput { id: gAddCharId; anchors.fill: parent; anchors.leftMargin: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                Text { anchors.left: parent.left; anchors.leftMargin: 6; anchors.verticalCenter: parent.verticalCenter; visible: gAddCharId.text.length === 0; text: "선택 사항"; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                            }
                        }
                        Text { text: "내용"; color: "#8080A0"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                        Rectangle {
                            width: parent.width; height: 64; radius: 4; color: "#181828"; border.color: "#2A2A40"; border.width: 1
                            TextEdit { id: gAddContent; anchors.fill: parent; anchors.margins: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; wrapMode: TextEdit.Wrap }
                            Text { anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 6; visible: gAddContent.text.length === 0; text: "프롬프트 가이드 내용..."; color: "#505070"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                        }
                        Rectangle {
                            width: 60; height: 24; radius: 4; color: gSaveHov.containsMouse ? "#1A5A3A" : "#143A28"; Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "저장"; color: "#60D090"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily }
                            MouseArea {
                                id: gSaveHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var cnt = gAddContent.text.trim()
                                    if (!cnt) return
                                    bridge.addPromptGuide(gAddModel.text.trim(), cnt, gAddCharId.text.trim())
                                    dbRoot.promptGuidesJson = bridge.getPromptGuidesDB()
                                    gAddModel.text = ""; gAddContent.text = ""; gAddCharId.text = ""
                                    dbRoot._guideAddFormOpen = false
                                }
                            }
                        }
                        Item { height: 4 }
                    }
                }

                ScrollView {
                    anchors.top: guideAddForm.bottom; anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                    clip: true; ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Column {
                        id: guidesCol
                        width: panel.width - 16; x: 8; spacing: 0

                        Text {
                            visible: dbRoot._guideGroups.length === 0
                            text: "저장된 프롬프트 가이드가 없습니다."
                            color: "#505070"; font.pixelSize: 12; font.family: dbRoot.fontFamily
                            topPadding: 20; leftPadding: 12
                        }

                        Repeater {
                            model: dbRoot._guideGroups
                            delegate: Column {
                                id: gGroup
                                width: guidesCol.width; spacing: 0
                                property bool _open: false

                                // 모델명 헤더
                                Rectangle {
                                    width: parent.width; height: 28
                                    color: ggHov.containsMouse ? "#1A1A2E" : "#131326"
                                    Behavior on color { ColorAnimation { duration: 100 } }

                                    Text { anchors.left: parent.left; anchors.leftMargin: 4; anchors.verticalCenter: parent.verticalCenter; text: gGroup._open ? "▾" : "▸"; color: "#6060A0"; font.pixelSize: 9 }
                                    Text { anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; anchors.right: ggBadge.left; anchors.rightMargin: 4; text: modelData.model_name; color: "#8080B0"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily; elide: Text.ElideRight }
                                    Rectangle {
                                        id: ggBadge
                                        anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                                        width: ggBadgeLbl.implicitWidth + 10; height: 16; radius: 8; color: "#252540"
                                        Text { id: ggBadgeLbl; anchors.centerIn: parent; text: modelData.guides.length + "개"; color: "#6060A0"; font.pixelSize: 9; font.family: dbRoot.fontFamily }
                                    }
                                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: "#1E1E34" }
                                    MouseArea { id: ggHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: gGroup._open = !gGroup._open }
                                }

                                Item {
                                    width: parent.width
                                    height: gGroup._open ? ggEntries.implicitHeight : 0
                                    clip: true
                                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                                    Column {
                                        id: ggEntries; width: parent.width; spacing: 4; topPadding: 4; bottomPadding: 4

                                        Repeater {
                                            model: modelData.guides
                                            delegate: Rectangle {
                                                id: gCard
                                                width: ggEntries.width - 4; x: 2; radius: 4; color: "#151523"; border.color: "#252540"; border.width: 1
                                                property bool _editing: false
                                                height: _editing ? gEditCol.implicitHeight + 16 : gViewCol.implicitHeight + 16
                                                Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                                                // 조회 모드
                                                Column {
                                                    id: gViewCol
                                                    anchors.top: parent.top; anchors.topMargin: 8
                                                    anchors.left: parent.left; anchors.leftMargin: 10
                                                    anchors.right: parent.right; anchors.rightMargin: 10
                                                    spacing: 4; visible: !gCard._editing

                                                    Row {
                                                        spacing: 6
                                                        Rectangle {
                                                            visible: (modelData.character_id || "").length > 0
                                                            width: gCharLbl.implicitWidth + 10; height: 16; radius: 8; color: "#252545"
                                                            Text { id: gCharLbl; anchors.centerIn: parent; text: modelData.character_id || ""; color: "#7070C0"; font.pixelSize: 9; font.family: dbRoot.fontFamily }
                                                        }
                                                    }

                                                    Text {
                                                        width: parent.width
                                                        text: modelData.content
                                                        color: "#C0C0D8"; font.pixelSize: 10; font.family: dbRoot.fontFamily
                                                        wrapMode: Text.Wrap; maximumLineCount: 6; elide: Text.ElideRight
                                                    }

                                                    Item {
                                                        width: parent.width; height: 22
                                                        Rectangle {
                                                            id: gDelBtn; width: 30; height: 20; radius: 4; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                                            color: gDelHov.containsMouse ? "#4A1A1A" : "transparent"; Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "삭제"; font.pixelSize: 9; color: "#A06060"; font.bold: true }
                                                            MouseArea { id: gDelHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    bridge.deletePromptGuide(modelData.id)
                                                                    dbRoot.promptGuidesJson = bridge.getPromptGuidesDB()
                                                                }
                                                            }
                                                        }
                                                        Rectangle {
                                                            width: 30; height: 20; radius: 4; anchors.right: gDelBtn.left; anchors.rightMargin: 2; anchors.verticalCenter: parent.verticalCenter
                                                            color: gEditHov.containsMouse ? "#2A3A5A" : "transparent"; Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "수정"; font.pixelSize: 9; color: "#7090C0"; font.bold: true }
                                                            MouseArea { id: gEditHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                onClicked: { gEditArea.text = modelData.content; gCard._editing = true }
                                                            }
                                                        }
                                                    }
                                                }

                                                // 수정 모드
                                                Column {
                                                    id: gEditCol
                                                    anchors.top: parent.top; anchors.topMargin: 8
                                                    anchors.left: parent.left; anchors.leftMargin: 10
                                                    anchors.right: parent.right; anchors.rightMargin: 10
                                                    spacing: 6; visible: gCard._editing

                                                    Rectangle {
                                                        width: parent.width; height: 64; radius: 4; color: "#181828"; border.color: "#3A3A60"; border.width: 1
                                                        TextEdit { id: gEditArea; anchors.fill: parent; anchors.margins: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: dbRoot.fontFamily; wrapMode: TextEdit.Wrap }
                                                    }
                                                    Row {
                                                        spacing: 6
                                                        Rectangle {
                                                            width: 50; height: 22; radius: 4; color: gConfHov.containsMouse ? "#1A5A3A" : "#143A28"; Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "저장"; color: "#60D090"; font.pixelSize: 10; font.bold: true; font.family: dbRoot.fontFamily }
                                                            MouseArea { id: gConfHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    bridge.updatePromptGuide(modelData.id, gEditArea.text.trim())
                                                                    dbRoot.promptGuidesJson = bridge.getPromptGuidesDB()
                                                                    gCard._editing = false
                                                                }
                                                            }
                                                        }
                                                        Rectangle {
                                                            width: 50; height: 22; radius: 4; color: gCancHov.containsMouse ? "#3A1A1A" : "#281414"; Behavior on color { ColorAnimation { duration: 100 } }
                                                            Text { anchors.centerIn: parent; text: "취소"; color: "#D06060"; font.pixelSize: 10; font.family: dbRoot.fontFamily }
                                                            MouseArea { id: gCancHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: gCard._editing = false }
                                                        }
                                                    }
                                                    Item { height: 2 }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Item { height: 8 }
                    }
                }
            }
        }
    }
}
