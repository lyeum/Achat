import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 표정 / 아이콘 지정 패널 — 전체 오버레이 모달
//
// 슬롯:
//   icon              → icons/{char_id}/{char_id}.png   (전신 아이콘)
//   emotion_{mood}    → icons/{char_id}/emotion/{mood}.png  (감정 레이어)
//
// 파일이 없으면 icons/default/emotion/{mood}.png 기본 이미지를 표시한다.
Item {
    id: emotRoot

    property string fontFamily:  ""
    property string characterId: ""   // bridge.characterId 와 연동

    signal closeRequested()

    // ── 감정 목록 ────────────────────────────────────────────────────────────
    readonly property var _emotions: [
        { key: "neutral",      label: "기본",   emoji: "😐" },
        { key: "happy",        label: "행복",   emoji: "😊" },
        { key: "affectionate", label: "애정",   emoji: "🥰" },
        { key: "touched",      label: "감동",   emoji: "🥹" },
        { key: "curious",      label: "호기심", emoji: "🤔" },
        { key: "sad",          label: "슬픔",   emoji: "😢" },
        { key: "embarrassed",  label: "당황",   emoji: "😳" },
        { key: "annoyed",      label: "짜증",   emoji: "😤" },
        { key: "angry",        label: "분노",   emoji: "😠" },
    ]

    // ── 상태 ─────────────────────────────────────────────────────────────────
    property string _iconUrl:          ""
    property int    _iconVersion:      0
    property var    _emotionVersions:  ({})  // mood → 캐시 무효화 카운터

    Component.onCompleted: _loadCurrentUrls()
    onCharacterIdChanged:  _loadCurrentUrls()

    function _loadCurrentUrls() {
        if (!characterId) { _iconUrl = ""; return }
        var iconPath = Qt.resolvedUrl(
            "../assets/icons/" + characterId + "/" + characterId + ".png"
        )
        _iconUrl = iconPath
        // emotion 버전은 0으로 리셋 (새 캐릭터)
        _emotionVersions = {}
    }

    // 해당 emotion의 URL 반환 (char 전용 → 없으면 default)
    function _emotionUrl(mood) {
        if (!characterId) return ""
        return Qt.resolvedUrl(
            "../assets/icons/" + characterId + "/emotion/" + mood + ".png"
        )
    }
    function _defaultEmotionUrl(mood) {
        return Qt.resolvedUrl("../assets/icons/default/emotion/" + mood + ".png")
    }

    // ── imageImported 수신 ──────────────────────────────────────────────────
    Connections {
        target: bridge
        function onImageImported(slotType, result) {
            if (slotType === "icon") {
                emotRoot._iconUrl    = result
                emotRoot._iconVersion++
            } else if (slotType.startsWith("emotion_")) {
                var mood = slotType.substring(8)  // "emotion_".length
                var v = Object.assign({}, emotRoot._emotionVersions)
                v[mood] = (v[mood] || 0) + 1
                emotRoot._emotionVersions = v
            }
        }
    }

    // ── 딤 배경 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000"; opacity: 0.65
        MouseArea { anchors.fill: parent; onClicked: emotRoot.closeRequested() }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: epanel
        anchors { fill: parent; margins: 10 }
        color: "#1A1A1A"
        radius: 12
        MouseArea { anchors.fill: parent; onClicked: {} }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // 헤더
            Rectangle {
                Layout.fillWidth: true
                height: 40; color: "#242424"; radius: 12
                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 12; color: parent.color
                }
                Text {
                    anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                    text: "표정 / 아이콘 지정"
                    color: "#E0E0E0"; font.pixelSize: 13; font.bold: true
                    font.family: emotRoot.fontFamily
                }
                Rectangle {
                    anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                    width: 20; height: 20; radius: 10
                    color: xHov.containsMouse ? "#C03030" : "#444"
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                    MouseArea {
                        id: xHov; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: emotRoot.closeRequested()
                    }
                }
            }

            // 스크롤 본문
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: epanel.width - 20
                    x: 10
                    spacing: 12

                    Item { Layout.preferredHeight: 4 }

                    // 전신 아이콘 슬롯
                    EmoSlotLabel { label: "전신 아이콘"; fontFam: emotRoot.fontFamily }

                    EmoSlot {
                        Layout.fillWidth: true
                        height: 160
                        slotType: "icon"
                        label: "아이콘 (icons/{캐릭터}/{캐릭터}.png)"
                        previewUrl: emotRoot._iconUrl !== ""
                            ? emotRoot._iconUrl + "#v" + emotRoot._iconVersion
                            : ""
                        fontFam: emotRoot.fontFamily
                    }

                    // 감정 표정 슬롯
                    EmoSlotLabel { label: "감정 표정"; fontFam: emotRoot.fontFamily }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 3
                        columnSpacing: 8
                        rowSpacing: 8

                        Repeater {
                            model: emotRoot._emotions
                            EmoSlot {
                                Layout.fillWidth: true
                                height: 110
                                slotType: "emotion_" + modelData.key
                                label: modelData.label
                                emoji: modelData.emoji
                                previewUrl: {
                                    var ver = emotRoot._emotionVersions[modelData.key] || 0
                                    var u = emotRoot._emotionUrl(modelData.key)
                                    return u ? u + "#v" + ver : ""
                                }
                                defaultUrl: emotRoot._defaultEmotionUrl(modelData.key)
                                fontFam: emotRoot.fontFamily
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 6 }
                }
            }

            // 하단 닫기
            Rectangle {
                Layout.fillWidth: true
                height: 44; color: "#242424"; radius: 12
                Rectangle {
                    anchors { top: parent.top; left: parent.left; right: parent.right }
                    height: 12; color: parent.color
                }
                RowLayout {
                    anchors { fill: parent; margins: 8 }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        width: 80; height: 28; radius: 6
                        color: closeBtn.containsMouse ? "#357ABD" : "#4A90D9"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent; text: "닫기"
                            color: "white"; font.pixelSize: 12; font.family: emotRoot.fontFamily
                        }
                        MouseArea {
                            id: closeBtn; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: emotRoot.closeRequested()
                        }
                    }
                }
            }
        }
    }

    // ── 인라인 컴포넌트 ───────────────────────────────────────────────────────

    component EmoSlotLabel: Text {
        property string label:   ""
        property string fontFam: ""
        Layout.fillWidth: true
        text: label
        color: "#4A90D9"; font.pixelSize: 12; font.bold: true
        font.family: fontFam
        leftPadding: 2
    }

    // 감정/아이콘 이미지 슬롯
    component EmoSlot: Rectangle {
        id: emoSlot
        property string slotType:  ""
        property string label:     ""
        property string emoji:     "😐"   // 이미지 없을 때 플레이스홀더 이모지
        property string previewUrl: ""    // char 전용 이미지 URL
        property string defaultUrl: ""    // 기본(default) 이미지 URL
        property string fontFam:   ""

        radius: 8
        color:  emoDrop.containsDrag ? "#1A3A6A"
                                     : (emoMa.containsMouse ? "#272727" : "#202020")
        border.color: emoDrop.containsDrag ? "#4A90D9"
                                           : (emoMa.containsMouse ? "#555" : "#333")
        border.width: 1
        Behavior on color        { ColorAnimation { duration: 100 } }
        Behavior on border.color { ColorAnimation { duration: 100 } }

        // char 전용 이미지
        Image {
            id: charImg
            anchors { top: parent.top; left: parent.left; right: parent.right
                      margins: 6; bottom: emoLabel.top; bottomMargin: 4 }
            source: emoSlot.previewUrl
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true; cache: false
            visible: emoSlot.previewUrl !== "" && status === Image.Ready
        }

        // default 이미지 (char 전용이 없을 때)
        Image {
            anchors { top: parent.top; left: parent.left; right: parent.right
                      margins: 6; bottom: emoLabel.top; bottomMargin: 4 }
            source: emoSlot.defaultUrl
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true; cache: false
            visible: !charImg.visible && emoSlot.defaultUrl !== "" && status === Image.Ready
        }

        // 플레이스홀더 (이미지 없을 때)
        Column {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -10
            visible: charImg.source === "" || charImg.status !== Image.Ready
            spacing: 4
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: emoSlot.emoji
                font.pixelSize: emoSlot.height > 130 ? 28 : 20
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "클릭 또는 드래그"
                color: "#444"; font.pixelSize: 9
                font.family: emoSlot.fontFam
            }
        }

        // 레이블
        Text {
            id: emoLabel
            anchors { bottom: parent.bottom; left: parent.left; right: parent.right; bottomMargin: 6 }
            text: emoSlot.label
            color: "#666"; font.pixelSize: 10
            font.family: emoSlot.fontFam
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            leftPadding: 4; rightPadding: 4
        }

        DropArea {
            id: emoDrop
            anchors.fill: parent
            onDropped: {
                if (drop.hasUrls && drop.urls.length > 0)
                    bridge.importImageFromDrop(emoSlot.slotType, drop.urls[0].toString())
            }
        }

        MouseArea {
            id: emoMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: bridge.browseImage(emoSlot.slotType)
        }
    }
}
