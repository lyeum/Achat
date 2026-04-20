import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 캐릭터 상태 패널 — 타이틀바 "상태" 버튼으로 열림
Item {
    id: statusRoot

    property string fontFamily: ""
    property string statusJson: "{}"   // bridge.getCharacterStatus() 결과

    signal closeRequested()

    // ── 파싱된 상태값 ─────────────────────────────────────────────────────────
    property var _data: {
        try {
            var raw = JSON.parse(statusRoot.statusJson)
            return {
                char_name:  raw.char_name  || "",
                mood:       raw.mood       || "neutral",
                affection:  raw.affection  !== undefined ? raw.affection  : 0,
                tier:       raw.tier       || "stranger",
                turn_count: raw.turn_count !== undefined ? raw.turn_count : 0
            }
        }
        catch(e) { return { char_name:"", mood:"neutral", affection:0, tier:"stranger", turn_count:0 } }
    }

    readonly property var _moodLabel: ({
        "neutral":      "😶 무관심",
        "happy":        "😊 기분 좋음",
        "affectionate": "😍 호감",
        "touched":      "😭 감동",
        "curious":      "🤔 호기심",
        "sad":          "😔 슬픔",
        "embarrassed":  "😳 당황",
        "annoyed":      "😤 짜증",
        "angry":        "😠 화남",
    })

    readonly property var _tierLabel: ({
        "stranger":     "감정 억제",
        "acquaintance": "드물게 반응",
        "familiar":     "자연스럽게 묻어남",
        "friendly":     "직접적 표현",
        "close":        "솔직한 반응",
        "intimate":     "즉각적·감추지 않음",
    })

    readonly property var _tierColor: ({
        "stranger":     "#666",
        "acquaintance": "#888",
        "familiar":     "#6A9",
        "friendly":     "#4A90D9",
        "close":        "#A06AD9",
        "intimate":     "#D96A6A",
    })

    // ── 배경 딤 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.5
        MouseArea {
            anchors.fill: parent
            onClicked: statusRoot.closeRequested()
        }
    }

    // ── 모달 박스 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: modal
        width: 300
        height: Math.min(modalHeader.height + 16 + contentLayout.implicitHeight + 16, statusRoot.height - 96)
        anchors {
            top: parent.top
            topMargin: 48
            horizontalCenter: parent.horizontalCenter
        }
        color: "#1A1A1A"
        radius: 12
        border.color: "#333"
        border.width: 1
        clip: true

        // 헤더
        Rectangle {
            id: modalHeader
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 38
            color: "#242424"
            radius: 12
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }
            Text {
                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                text: "캐릭터 상태"
                color: "#E0E0E0"; font.pixelSize: 13; font.bold: true
                font.family: statusRoot.fontFamily
            }
            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                width: 20; height: 20; radius: 10
                color: closeHov.containsMouse ? "#C03030" : "#444"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                MouseArea {
                    id: closeHov; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: statusRoot.closeRequested()
                }
            }
        }

        // ── 컨텐츠 ───────────────────────────────────────────────────────────
        ColumnLayout {
            id: contentLayout
            anchors { top: modalHeader.bottom; left: parent.left; right: parent.right;
                      topMargin: 16; leftMargin: 16; rightMargin: 16 }
            spacing: 14

            // 캐릭터 이름
            Text {
                Layout.fillWidth: true
                text: statusRoot._data.char_name || "-"
                color: "#E0E0E0"; font.pixelSize: 15; font.bold: true
                font.family: statusRoot.fontFamily
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            // Tier 배지
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: tierLabel.implicitWidth + 20; height: 22; radius: 11
                color: Qt.rgba(0, 0, 0, 0)
                border.color: statusRoot._tierColor[statusRoot._data.tier] || "#666"
                border.width: 1
                Text {
                    id: tierLabel
                    anchors.centerIn: parent
                    text: statusRoot._tierLabel[statusRoot._data.tier] || statusRoot._data.tier
                    color: statusRoot._tierColor[statusRoot._data.tier] || "#888"
                    font.pixelSize: 11; font.family: statusRoot.fontFamily
                }
            }

            // ── 친밀도 바 ─────────────────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "친밀도"
                        color: "#888"; font.pixelSize: 11
                        font.family: statusRoot.fontFamily
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: statusRoot._data.affection + " / 100"
                        color: "#AAA"; font.pixelSize: 11
                        font.family: statusRoot.fontFamily
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 6; radius: 3
                    color: "#2A2A2A"
                    Rectangle {
                        width: parent.width * (statusRoot._data.affection / 100)
                        height: parent.height; radius: parent.radius
                        color: statusRoot._tierColor[statusRoot._data.tier] || "#4A90D9"
                        Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutQuad } }
                    }
                }
            }

            // ── mood ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "감정"
                    color: "#888"; font.pixelSize: 11
                    font.family: statusRoot.fontFamily
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: statusRoot._moodLabel[statusRoot._data.mood] || statusRoot._data.mood
                    color: "#D0D0D0"; font.pixelSize: 12
                    font.family: statusRoot.fontFamily
                }
            }

            // ── 대화 횟수 ────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "대화 횟수"
                    color: "#888"; font.pixelSize: 11
                    font.family: statusRoot.fontFamily
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: statusRoot._data.turn_count + " 턴"
                    color: "#D0D0D0"; font.pixelSize: 12
                    font.family: statusRoot.fontFamily
                }
            }

            Item { height: 2; width: 1 }
        }
    }
}
