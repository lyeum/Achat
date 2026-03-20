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
    signal customizationRequested()

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
        width: 210
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
            // 하단 코너만 직각으로
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

            // 닫기 버튼
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

            ColumnLayout {
                width: panel.width - 16
                x: 8
                spacing: 0

                // ── 캐릭터 섹션 ───────────────────────────────────────────────
                SectionLabel { label: "캐릭터"; fontFamily: settingsRoot.fontFamily }

                Repeater {
                    model: {
                        try { return JSON.parse(settingsRoot.characterListJson) }
                        catch(e) { return [] }
                    }
                    delegate: SettingsButton {
                        Layout.fillWidth: true
                        label: modelData.name || modelData.id
                        fontFamily: settingsRoot.fontFamily
                        onActivated: {
                            bridge.changeCharacter(modelData.id)
                            settingsRoot.closeRequested()
                        }
                    }
                }

                // ── 시나리오 섹션 ─────────────────────────────────────────────
                SectionLabel { label: "시나리오"; fontFamily: settingsRoot.fontFamily }

                // world→scenario→act 3중 nested 대신 flat 목록으로 구성
                // 각 항목: { type: "header"|"act", world_id, scenario_id, act_id, location }
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
                        Layout.fillWidth: true
                        height: modelData.type === "header" ? 20 : 28

                        // 세계관 헤더 레이블
                        Text {
                            visible: modelData.type === "header"
                            anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 4 }
                            text: modelData.world_id
                            color: "#888"; font.pixelSize: 10
                            font.family: settingsRoot.fontFamily
                        }

                        // Act 선택 버튼 — modelData에 world_id/scenario_id 포함되어 있으므로 parent 참조 불필요
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

                // ── 커스터마이징 섹션 ────────────────────────────────────────
                SectionLabel { label: "커스터마이징"; fontFamily: settingsRoot.fontFamily }

                SettingsButton {
                    Layout.fillWidth: true
                    label: "캐릭터 커스터마이징..."
                    fontFamily: settingsRoot.fontFamily
                    onActivated: {
                        settingsRoot.closeRequested()
                        settingsRoot.customizationRequested()
                    }
                }

                Item { Layout.preferredHeight: 8 }
            }
        }
    }

    // ── 내부 재사용 컴포넌트 ──────────────────────────────────────────────────

    component SectionLabel: Text {
        property string label: ""
        property string fontFamily: ""
        Layout.fillWidth: true
        Layout.topMargin: 10
        Layout.bottomMargin: 4
        text: label
        color: "#4A90D9"
        font.pixelSize: 10
        font.bold: true
        font.family: fontFamily
        leftPadding: 4
    }

    component SettingsButton: Rectangle {
        property string label: ""
        property string fontFamily: ""
        signal activated()
        height: 28
        radius: 6
        color: btnHover.containsMouse ? "#2E2E2E" : "transparent"
        Behavior on color { ColorAnimation { duration: 100 } }

        Text {
            anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 8; right: parent.right; rightMargin: 8 }
            text: parent.label
            color: "#D0D0D0"
            font.pixelSize: 11
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
