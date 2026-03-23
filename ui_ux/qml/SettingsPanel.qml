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

    signal closeRequested()
    signal emotionPanelRequested()
    signal characterBuildRequested()
    signal newSessionRequested(bool keepMemory)

    // ── 섹션 펼침 상태 ────────────────────────────────────────────────────────
    property bool secCharExpanded:   true   // 캐릭터: 기본 펼침
    property bool secWorldExpanded:  false
    property bool secCustomExpanded: false
    property bool secSessionExpanded: false

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

            Text {
                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                text: "설정"
                color: "#E0E0E0"
                font.pixelSize: 13
                font.bold: true
                font.family: settingsRoot.fontFamily
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

                        Repeater {
                            model: {
                                try { return JSON.parse(settingsRoot.characterListJson) }
                                catch(e) { return [] }
                            }
                            delegate: SettingsButton {
                                width: charCol.width
                                label: modelData.name || modelData.id
                                fontFamily: settingsRoot.fontFamily
                                onActivated: {
                                    bridge.changeCharacter(modelData.id)
                                    settingsRoot.closeRequested()
                                }
                            }
                        }
                    }
                }

                // ══════════════════════════════════════════════════════════════
                // 시나리오 섹션
                // ══════════════════════════════════════════════════════════════
                SectionHeader {
                    label: "시나리오"
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

                        Repeater {
                            model: {
                                try {
                                    var worlds = JSON.parse(settingsRoot.worldListJson)
                                    var items = []
                                    for (var i = 0; i < worlds.length; i++) {
                                        var w = worlds[i]
                                        items.push({ type: "header", world_id: w.world_id,
                                                     scenario_id: "", act_id: "", location: "" })
                                        for (var j = 0; j < w.scenarios.length; j++) {
                                            var sc = w.scenarios[j]
                                            for (var k = 0; k < sc.acts.length; k++) {
                                                var a = sc.acts[k]
                                                items.push({ type: "act",
                                                             world_id: w.world_id,
                                                             scenario_id: sc.scenario_id,
                                                             act_id: a.act_id,
                                                             location: a.location || "" })
                                            }
                                        }
                                    }
                                    return items
                                } catch(e) { return [] }
                            }
                            delegate: Item {
                                width: worldCol.width
                                height: modelData.type === "header" ? 20 : 28

                                Text {
                                    visible: modelData.type === "header"
                                    anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 4 }
                                    text: modelData.world_id
                                    color: "#888"; font.pixelSize: 12
                                    font.family: settingsRoot.fontFamily
                                }

                                SettingsButton {
                                    visible: modelData.type === "act"
                                    anchors.fill: parent
                                    label: "  " + modelData.act_id
                                           + (modelData.location ? "  (" + modelData.location + ")" : "")
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

                        SettingsButton {
                            width: sessionCol.width
                            label: "새 대화 시작 (기억 초기화)"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.newSessionRequested(false)
                            }
                        }

                        SettingsButton {
                            width: sessionCol.width
                            label: "새 대화 시작 (기억 유지)"
                            fontFamily: settingsRoot.fontFamily
                            onActivated: {
                                settingsRoot.closeRequested()
                                settingsRoot.newSessionRequested(true)
                            }
                        }
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
