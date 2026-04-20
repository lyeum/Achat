import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 설정 패널 — 오른쪽에서 슬라이드인
// 부모 컨테이너 안에 z:10 오버레이로 배치
Item {
    id: settingsRoot

    property string fontFamily: ""
    // bridge.getCharacterList() / getWorldList() 반환 JSON 문자열
    property string characterListJson: "[]"
    property string worldListJson:     "[]"
    property string currentTheme:     "dark"
    property string currentCharId:    ""    // bridge.characterId — 현재 활성 캐릭터 (삭제 불가)

    property string sessionListJson: "[]"   // bridge.listSessions(char_id) 결과
    property string activeSessionId: ""    // 현재 활성 session_id

    signal closeRequested()
    signal emotionPanelRequested()
    signal characterBuildRequested()
    signal characterCreateRequested()
    signal newSessionRequested(bool keepMemory)
    signal resetConfirmRequested()
    signal themeChangeRequested(string themeId)
    signal memoryDBRequested()
    signal adminRequested()
    signal sessionSwitchRequested(string sessionId)
    signal worldCreateRequested()
    signal windowScaleChangeRequested(int scaleIdx)

    // ── 섹션 펼침 상태 ────────────────────────────────────────────────────────
    property bool secCharExpanded:   true   // 캐릭터: 기본 펼침
    property bool secWorldExpanded:  false
    property bool secCustomExpanded: false
    property bool secSessionExpanded: false
    property bool secThemeExpanded:  false
    property bool secDataExpanded:   false  // 데이터 섹션
    property bool secDisplayExpanded: false // 화면 섹션
    property bool secPipExpanded:    false  // PIP 모드 섹션

    property int    currentWindowScale: 1   // 0=소형, 1=중형, 2=대형
    property string pipBubbleDir:  "random" // "random" | "left" | "right"

    signal pipBubbleDirChangeRequested(string dir)

    // ── 배경 딤 (클릭으로 닫기) ──────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.4
        MouseArea {
            anchors.fill: parent
            onClicked: settingsRoot.closeRequested()
        }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panel
        width: 250
        anchors {
            top: parent.top
            bottom: parent.bottom
            right: parent.right
        }
        color: "#1A1A1A"
        radius: 12

        // 헤더
        Rectangle {
            id: header
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 38
            color: "#242424"
            radius: 12
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 12
                color: parent.color
            }

            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                width: 20; height: 20; radius: 10
                color: closeHover.containsMouse ? "#C03030" : "#444"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                MouseArea {
                    id: closeHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: settingsRoot.closeRequested()
                }
            }
        }

        // 스크롤 목록
        ScrollView {
            anchors {
                top: header.bottom
                bottom: parent.bottom
                left: parent.left
                right: parent.right
                topMargin: 4
                bottomMargin: 8
            }
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            Column {
                width: panel.width - 16
                x: 8
                spacing: 0

                // ══════════════════════════════════════════════════════════════
                // 캐릭터 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "캐릭터"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secCharExpanded
                    onToggled: settingsRoot.secCharExpanded = !settingsRoot.secCharExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secCharExpanded ? charCol.implicitHeight : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: charCol
                        width: parent.width
                        spacing: 0

                        SettingsButton {
                            width: charCol.width
                            label: "+ 캐릭터 생성"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.characterCreateRequested()
                            }
                        }

                        SettingsButton {
                            width: charCol.width
                            label: "+ 캐릭터 초기화"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.resetConfirmRequested()
                            }
                        }

                        Repeater {
                            model: {
                                try { return JSON.parse(settingsRoot.characterListJson) }
                                catch(e) { return [] }
                            }
                            delegate: Item {
                                width: charCol.width
                                height: 32

                                // 캐릭터 이름 버튼 (삭제 버튼 공간 제외)
                                SettingsButton {
                                    anchors { left: parent.left; right: charDelBtn.left; rightMargin: 2; top: parent.top; bottom: parent.bottom }
                                    label: modelData.name || modelData.id
                                    fontFamily: settingsRoot.fontFamily
                                    onActivated: {
                                        bridge.changeCharacter(modelData.id)
                                        var dw = bridge.getDefaultWorld()
                                        try {
                                            var d = JSON.parse(dw)
                                            if (d.world_id && d.scenario_id && d.act_id)
                                                bridge.changeWorld(d.world_id, d.scenario_id, d.act_id)
                                        } catch(e) {}
                                        settingsRoot.closeRequested()
                                    }
                                }

                                // 삭제 버튼 — 현재 활성 캐릭터는 숨김
                                Rectangle {
                                    id: charDelBtn
                                    visible: modelData.id !== settingsRoot.currentCharId
                                    width: visible ? 38 : 0
                                    height: 24; radius: 4
                                    anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                                    color: charDelHov.containsMouse ? "#802020" : "#3A1818"
                                    Behavior on color { ColorAnimation { duration: 100 } }
                                    Text { anchors.centerIn: parent; text: "삭제"; color: "#E08080"; font.pixelSize: 10; font.family: settingsRoot.fontFamily }
                                    MouseArea {
                                        id: charDelHov; anchors.fill: parent
                                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            bridge.deleteCharacter(modelData.id)
                                            settingsRoot.characterListJson = bridge.getCharacterList()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ══════════════════════════════════════════════════════════════
                // 세계관 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "세계관"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secWorldExpanded
                    onToggled: settingsRoot.secWorldExpanded = !settingsRoot.secWorldExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secWorldExpanded ? worldCol.implicitHeight : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: worldCol
                        width: parent.width
                        spacing: 0

                        SettingsButton {
                            width: worldCol.width
                            label: "+ 세계관 생성"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.worldCreateRequested()
                            }
                        }

                        // 세계관별 드릴다운 (세계관 헤더 클릭 → act 목록 펼침)
                        Repeater {
                            model: {
                                try { return JSON.parse(settingsRoot.worldListJson) }
                                catch(e) { return [] }
                            }
                            delegate: Column {
                                id: worldDelegate
                                width: worldCol.width
                                spacing: 0
                                property bool _expanded: false

                                // 세계관 헤더 행
                                Rectangle {
                                    width: worldDelegate.width
                                    height: 28
                                    color: worldHov.containsMouse ? "#242424" : "transparent"
                                    Behavior on color { ColorAnimation { duration: 100 } }
                                    radius: 4

                                    Text {
                                        id: wArrow
                                        anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 4 }
                                        text: worldDelegate._expanded ? "▾" : "▸"
                                        color: "#6060A0"; font.pixelSize: 9
                                    }
                                    Text {
                                        anchors { verticalCenter: parent.verticalCenter; left: wArrow.right; leftMargin: 4 }
                                        text: modelData.world_id
                                        color: "#9090C0"; font.pixelSize: 12; font.bold: true
                                        font.family: settingsRoot.fontFamily
                                        elide: Text.ElideRight
                                    }
                                    MouseArea {
                                        id: worldHov; anchors.fill: parent; hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: worldDelegate._expanded = !worldDelegate._expanded
                                    }
                                }

                                // act 목록 (펼쳐질 때만 표시)
                                Item {
                                    width: worldDelegate.width
                                    height: worldDelegate._expanded ? actsInner.implicitHeight : 0
                                    clip: true
                                    Behavior on height { NumberAnimation { duration: 120; easing.type: Easing.InOutQuad } }

                                    Column {
                                        id: actsInner
                                        width: parent.width
                                        spacing: 0

                                        Repeater {
                                            model: {
                                                var items = []
                                                for (var j = 0; j < modelData.scenarios.length; j++) {
                                                    var sc = modelData.scenarios[j]
                                                    for (var k = 0; k < sc.acts.length; k++) {
                                                        var a = sc.acts[k]
                                                        items.push({
                                                            world_id:     modelData.world_id,
                                                            scenario_id:  sc.scenario_id,
                                                            act_id:       a.act_id,
                                                            location:     a.location || "",
                                                            display_name: a.display_name || ""
                                                        })
                                                    }
                                                }
                                                return items
                                            }
                                            delegate: SettingsButton {
                                                width: actsInner.width
                                                label: "    " + (modelData.display_name
                                                       ? modelData.display_name + (modelData.location ? " (" + modelData.location + ")" : "")
                                                       : modelData.location || modelData.act_id)
                                                fontFamily: settingsRoot.fontFamily
                                                onActivated: {
                                                    bridge.changeWorld(modelData.world_id,
                                                                       modelData.scenario_id,
                                                                       modelData.act_id)
                                                    settingsRoot.closeRequested()
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ══════════════════════════════════════════════════════════════
                // 커스터마이징 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "커스터마이징"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secCustomExpanded
                    onToggled: settingsRoot.secCustomExpanded = !settingsRoot.secCustomExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secCustomExpanded ? customCol.implicitHeight : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: customCol
                        width: parent.width
                        spacing: 0

                        SettingsButton {
                            width: customCol.width
                            label: "표정 / 아이콘 지정"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.emotionPanelRequested()
                            }
                        }

                        SettingsButton {
                            width: customCol.width
                            label: "캐릭터 커스텀"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.characterBuildRequested()
                            }
                        }
                    }
                }

                // ── 그룹 구분선 1 (캐릭터/세계관/커스터마이징 ↔ 세션관리/DB) ─────────
                Item { width: 1; height: 4 }
                Rectangle { width: parent.width; height: 1; color: "#2A2A3A" }
                Item { width: 1; height: 4 }

                // ══════════════════════════════════════════════════════════════
                // 세션 관리 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "세션 관리"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secSessionExpanded
                    onToggled: settingsRoot.secSessionExpanded = !settingsRoot.secSessionExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secSessionExpanded ? sessionCol.implicitHeight : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: sessionCol
                        width: parent.width
                        spacing: 0

                        // ── 새 세션 버튼들 ─────────────────────────────────────
                        SettingsButton {
                            width: sessionCol.width
                            label: "+ 새 대화 (기억 초기화)"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.newSessionRequested(false)
                            }
                        }

                        SettingsButton {
                            width: sessionCol.width
                            label: "+ 새 대화 (기억 유지)"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.newSessionRequested(true)
                            }
                        }

                        // ── 과거 세션 목록 ─────────────────────────────────────
                        Repeater {
                            model: {
                                try { return JSON.parse(settingsRoot.sessionListJson) }
                                catch(e) { return [] }
                            }
                            delegate: Item {
                                width: sessionCol.width
                                height: 36

                                // 날짜 + 세션 ID 요약
                                Rectangle {
                                    anchors { left: parent.left; right: sessBtnRow.left; rightMargin: 4; top: parent.top; bottom: parent.bottom }
                                    color: "transparent"

                                    Column {
                                        anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                                        spacing: 2

                                        Text {
                                            text: modelData.display_name || (modelData.session_id || "").substring(0, 18)
                                            color: modelData.session_id === settingsRoot.activeSessionId ? "#A0A0F0" : "#909090"
                                            font.pixelSize: 11; font.bold: modelData.session_id === settingsRoot.activeSessionId
                                            font.family: settingsRoot.fontFamily
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: (modelData.last_active || "").substring(0, 10)
                                            color: "#505070"; font.pixelSize: 9
                                            font.family: settingsRoot.fontFamily
                                        }
                                    }

                                    // 현재 활성 표시
                                    Rectangle {
                                        visible: modelData.session_id === settingsRoot.activeSessionId
                                        anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                                        width: curLbl.implicitWidth + 8; height: 16; radius: 8; color: "#252548"
                                        Text { id: curLbl; anchors.centerIn: parent; text: "현재"; color: "#8080C0"; font.pixelSize: 9; font.family: settingsRoot.fontFamily }
                                    }
                                }

                                // 전환 / 삭제 버튼 (현재 세션은 비활성)
                                Row {
                                    id: sessBtnRow
                                    visible: modelData.session_id !== settingsRoot.activeSessionId
                                    anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                                    spacing: 3

                                    Rectangle {
                                        width: 34; height: 24; radius: 4
                                        color: sessHov.containsMouse ? "#2A3A5A" : "#1A2A40"
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Text { anchors.centerIn: parent; text: "전환"; color: "#6090C0"; font.pixelSize: 10; font.family: settingsRoot.fontFamily }
                                        MouseArea {
                                            id: sessHov; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor; preventStealing: true
                                            onClicked: {
                                                settingsRoot.sessionSwitchRequested(modelData.session_id)
                                                settingsRoot.closeRequested()
                                            }
                                        }
                                    }

                                    Rectangle {
                                        width: 30; height: 24; radius: 4
                                        color: sessDelHov.containsMouse ? "#802020" : "#3A1818"
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Text { anchors.centerIn: parent; text: "삭제"; color: "#E08080"; font.pixelSize: 10; font.family: settingsRoot.fontFamily }
                                        MouseArea {
                                            id: sessDelHov; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor; preventStealing: true
                                            onClicked: {
                                                bridge.deleteSession(modelData.session_id)
                                                settingsRoot.sessionListJson = bridge.listSessions(bridge.characterId)
                                            }
                                        }
                                    }
                                }

                                Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: "#1A1A2E" }
                            }
                        }
                    }
                }

                // ── 그룹 구분선 2 (세션관리/DB ↔ 테마/해상도변경) ──────────────────
                Item { width: 1; height: 4 }
                Rectangle { width: parent.width; height: 1; color: "#2A2A3A" }
                Item { width: 1; height: 4 }

                // ══════════════════════════════════════════════════════════════
                // 테마 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "테마"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secThemeExpanded
                    onToggled: settingsRoot.secThemeExpanded = !settingsRoot.secThemeExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secThemeExpanded ? themeArea.implicitHeight + 12 : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: themeArea
                        width: parent.width
                        spacing: 0

                        Item { width: 1; height: 6 }

                        // ── 스와치 행 ─────────────────────────────────────────
                        Item {
                            width: parent.width
                            height: 72

                            Row {
                                anchors { left: parent.left; right: parent.right;
                                          leftMargin: 8; rightMargin: 8 }
                                spacing: 6

                                // 오션
                                Rectangle {
                                    width: (parent.width - 12) / 3
                                    height: 64; radius: 8
                                    color: "#0E1C22"
                                    border.color: settingsRoot.currentTheme === "ocean" ? "#FFFFFF" : "transparent"
                                    border.width: 2
                                    Behavior on border.color { ColorAnimation { duration: 150 } }

                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Rectangle {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            width: 18; height: 18; radius: 9
                                            color: "#5A9EA8"
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: "오션"
                                            color: "#A8D0D8"; font.pixelSize: 10
                                            font.family: settingsRoot.fontFamily
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: settingsRoot.themeChangeRequested("ocean")
                                    }
                                }

                                // 솔라
                                Rectangle {
                                    width: (parent.width - 12) / 3
                                    height: 64; radius: 8
                                    color: "#1C1610"
                                    border.color: settingsRoot.currentTheme === "solar" ? "#FFFFFF" : "transparent"
                                    border.width: 2
                                    Behavior on border.color { ColorAnimation { duration: 150 } }

                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Rectangle {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            width: 18; height: 18; radius: 9
                                            color: "#A07830"
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: "솔라"
                                            color: "#D8C898"; font.pixelSize: 10
                                            font.family: settingsRoot.fontFamily
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: settingsRoot.themeChangeRequested("solar")
                                    }
                                }

                                // 포레스트
                                Rectangle {
                                    width: (parent.width - 12) / 3
                                    height: 64; radius: 8
                                    color: "#101810"
                                    border.color: settingsRoot.currentTheme === "forest" ? "#FFFFFF" : "transparent"
                                    border.width: 2
                                    Behavior on border.color { ColorAnimation { duration: 150 } }

                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Rectangle {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            width: 18; height: 18; radius: 9
                                            color: "#5A8A68"
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: "포레스트"
                                            color: "#A8C8B0"; font.pixelSize: 10
                                            font.family: settingsRoot.fontFamily
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: settingsRoot.themeChangeRequested("forest")
                                    }
                                }
                            }
                        }
                    }
                }

                // ══════════════════════════════════════════════════════════════
                // DB 섹션 (기억 DB)
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "DB"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secDataExpanded
                    onToggled: settingsRoot.secDataExpanded = !settingsRoot.secDataExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secDataExpanded ? dataCol.implicitHeight : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: dataCol
                        width: parent.width
                        spacing: 0

                        SettingsButton {
                            width: dataCol.width
                            label: "DB 조회 / 편집"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.memoryDBRequested()
                            }
                        }
                    }
                }

                // ══════════════════════════════════════════════════════════════
                // 해상도 변경 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "해상도 변경"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secDisplayExpanded
                    onToggled: settingsRoot.secDisplayExpanded = !settingsRoot.secDisplayExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secDisplayExpanded ? displayCol.implicitHeight + 12 : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: displayCol
                        width: parent.width
                        spacing: 0

                        Item { width: 1; height: 8 }

                        // 해상도 크기 선택 버튼 3개
                        Item {
                            width: parent.width
                            height: 36

                            Row {
                                anchors { left: parent.left; right: parent.right;
                                          leftMargin: 8; rightMargin: 8 }
                                spacing: 6

                                Repeater {
                                    model: [
                                        { label: "소형", idx: 0, desc: "432×624" },
                                        { label: "중형", idx: 1, desc: "520×760" },
                                        { label: "대형", idx: 2, desc: "620×900" },
                                    ]
                                    Rectangle {
                                        width: (parent.width - 12) / 3
                                        height: 28; radius: 6
                                        color: settingsRoot.currentWindowScale === modelData.idx
                                               ? "#357ABD" : (scaleHov.containsMouse ? "#2E2E2E" : "#242424")
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        border.color: settingsRoot.currentWindowScale === modelData.idx
                                                      ? "#4A90D9" : "transparent"
                                        border.width: 1

                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 1
                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                text: modelData.label
                                                color: settingsRoot.currentWindowScale === modelData.idx
                                                       ? "white" : "#AAA"
                                                font.pixelSize: 11; font.bold: settingsRoot.currentWindowScale === modelData.idx
                                                font.family: settingsRoot.fontFamily
                                            }
                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                text: modelData.desc
                                                color: settingsRoot.currentWindowScale === modelData.idx
                                                       ? "#A8D0FF" : "#555"
                                                font.pixelSize: 9
                                                font.family: settingsRoot.fontFamily
                                            }
                                        }
                                        MouseArea {
                                            id: scaleHov
                                            anchors.fill: parent
                                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                settingsRoot.currentWindowScale = modelData.idx
                                                settingsRoot.windowScaleChangeRequested(modelData.idx)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }

                // ══════════════════════════════════════════════════════════════
                // PIP 모드 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "PIP 모드"
                    fontFamily: settingsRoot.fontFamily
                    expanded: settingsRoot.secPipExpanded
                    onToggled: settingsRoot.secPipExpanded = !settingsRoot.secPipExpanded
                }

                Item {
                    width: parent.width
                    height: settingsRoot.secPipExpanded ? pipCol.implicitHeight + 12 : 0
                    clip: true
                    Behavior on height { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }

                    Column {
                        id: pipCol
                        width: parent.width
                        spacing: 0

                        Item { width: 1; height: 8 }

                        // 말풍선 방향 레이블
                        Text {
                            x: 8
                            text: "말풍선 방향"
                            color: "#888"; font.pixelSize: 11
                            font.family: settingsRoot.fontFamily
                        }

                        Item { width: 1; height: 6 }

                        // 방향 선택 버튼 3개
                        Item {
                            width: parent.width
                            height: 30

                            Row {
                                anchors { left: parent.left; right: parent.right;
                                          leftMargin: 8; rightMargin: 8 }
                                spacing: 6

                                Repeater {
                                    model: [
                                        { label: "랜덤", dir: "random" },
                                        { label: "왼쪽", dir: "left"   },
                                        { label: "오른쪽", dir: "right" },
                                    ]
                                    Rectangle {
                                        width: (parent.width - 12) / 3
                                        height: 26; radius: 6
                                        color: settingsRoot.pipBubbleDir === modelData.dir
                                               ? "#357ABD" : (pipDirHov.containsMouse ? "#2E2E2E" : "#242424")
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        border.color: settingsRoot.pipBubbleDir === modelData.dir
                                                      ? "#4A90D9" : "transparent"
                                        border.width: 1

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: settingsRoot.pipBubbleDir === modelData.dir ? "white" : "#AAA"
                                            font.pixelSize: 11
                                            font.bold: settingsRoot.pipBubbleDir === modelData.dir
                                            font.family: settingsRoot.fontFamily
                                        }
                                        MouseArea {
                                            id: pipDirHov
                                            anchors.fill: parent
                                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                settingsRoot.pipBubbleDir = modelData.dir
                                                settingsRoot.pipBubbleDirChangeRequested(modelData.dir)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }

                Item { height: 8; width: 1 }
            }
        }
    }

    // ── 내부 재사용 컴포넌트 ──────────────────────────────────────────────────

    component SectionHeader: Rectangle {
        property string label: ""
        property string fontFamily: ""
        property bool expanded: false
        signal toggled()

        width: parent ? parent.width : 0
        height: 30
        color: secHov.containsMouse ? "#242424" : "transparent"
        Behavior on color { ColorAnimation { duration: 100 } }

        Text {
            id: secArrow
            anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 4 }
            text: parent.expanded ? "▾" : "▸"
            color: "#4A90D9"
            font.pixelSize: 10
        }
        Text {
            anchors { verticalCenter: parent.verticalCenter; left: secArrow.right; leftMargin: 4 }
            text: parent.label
            color: "#4A90D9"
            font.pixelSize: 13
            font.bold: true
            font.family: parent.fontFamily
        }
        MouseArea {
            id: secHov
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.toggled()
        }
    }

    component SettingsButton: Rectangle {
        property string label: ""
        property string fontFamily: ""
        signal activated()
        height: 32
        radius: 6
        color: btnHover.containsMouse ? "#2E2E2E" : "transparent"
        Behavior on color { ColorAnimation { duration: 100 } }

        Text {
            anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 8; right: parent.right; rightMargin: 8 }
            text: parent.label
            color: "#D0D0D0"
            font.pixelSize: 13
            font.family: parent.fontFamily
            elide: Text.ElideRight
        }

        MouseArea {
            id: btnHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.activated()
        }
    }
}
