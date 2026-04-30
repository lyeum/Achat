import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 캐릭터 생성 패널 — CharacterSelectPanel "+" 버튼으로 열림
// character_schema.yaml 구조에 맞는 폼 입력 UI
Item {
    id: createRoot

    property string fontFamily: ""

    signal closeRequested()
    signal saveRequested(string jsonData)  // bridge.saveNewCharacter()로 전달

    // ── 공용 색상 ──────────────────────────────────────────────────────────
    readonly property color _bg:       "#131320"
    readonly property color _bgInput:  "#1C1C30"
    readonly property color _bgSel:    "#252545"
    readonly property color _border:   "#2A2A42"
    readonly property color _accent:   "#5A5ACA"
    readonly property color _textPri:  "#C0C0E0"
    readonly property color _textSec:  "#606080"

    // ── 입력 상태 ─────────────────────────────────────────────────────────
    property string f_id:          ""
    property string f_name:        ""
    property string f_description: ""
    property string f_formality:   "반말"   // 반말 | 존댓말
    property string f_style:       "blunt"  // blunt | soft
    property string f_persona:     "quiet_sensitive"
    property string f_personality: "calm"

    // 규칙 목록
    property var f_rules: [
        "캐릭터를 벗어나는 발언을 하지 않는다.",
        "AI임을 인정하거나 암시하는 발언을 하지 않는다.",
        "올바른 한국어 문법을 사용한다."
    ]

    // 대화 파라미터 (response_length per tier)
    property var f_rl: ({ stranger:0.1, acquaintance:0.2, familiar:0.4, friendly:0.55, close:0.65, intimate:0.75 })
    property var f_op: ({ stranger:0.05, acquaintance:0.15, familiar:0.3, friendly:0.45, close:0.6, intimate:0.75 })
    property real f_dr: 0.6

    property string _saveError: ""

    readonly property var _tiers:   ["stranger", "acquaintance", "familiar", "friendly", "close", "intimate"]
    readonly property var _tierKo:  ["낯선(0-15)", "지인(16-30)", "아는(31-50)", "친한(51-70)", "친밀(71-85)", "신뢰(86-100)"]

    // ── 헬퍼 ────────────────────────────────────────────────────────────
    function _buildJson() {
        var rl = {}; var op = {}
        for (var i = 0; i < _tiers.length; i++) {
            rl[_tiers[i]] = f_rl[_tiers[i]]
            op[_tiers[i]] = f_op[_tiers[i]]
        }

        // 친밀도 tier 텍스트 — formality에 따라 분기
        var affection
        if (f_formality === "존댓말") {
            affection = {
                stranger:     "처음 만난 사이. 필요한 말만 정중하게 한다. 감정적 반응은 거의 보이지 않는다.",
                acquaintance: "아는 사이지만 거리감을 유지한다. 공손하게 응대하고 개인적인 이야기는 피한다.",
                familiar:     "조금 편해진 상태. 여전히 존댓말을 유지하며 자연스럽게 대화한다.",
                friendly:     "자연스럽게 대화한다. 배려가 정중한 말 속에 드러나기 시작한다.",
                close:        "신뢰가 생긴 상태. 솔직한 반응을 보이되 존댓말을 유지한다.",
                intimate:     "깊은 신뢰 상태. 감정을 솔직하게 표현하되 존댓말을 유지한다."
            }
        } else {
            affection = {
                stranger:     "처음 만난 사이. 대화를 짧게 끊으려 하고 개인적인 반응을 거의 하지 않는다.",
                acquaintance: "기본 대화는 가능하지만 경계가 있다. 개인적인 이야기는 아직 조심스럽다.",
                familiar:     "조금 편해진 상태. 가끔 관심이 묻어나오지만 여전히 담담하다.",
                friendly:     "자연스럽게 대화한다. 배려가 짧은 말 속에 드러나기 시작한다.",
                close:        "배려가 자연스럽게 드러난다. 솔직한 반응을 자주 보인다.",
                intimate:     "깊은 신뢰 상태. 감정을 짧게라도 솔직하게 표현한다."
            }
        }

        var emotion = {
            happy:        "현재 기분이 좋은 상태. 반응이 약간 빨라지고 말이 조금 더 나온다.",
            sad:          "현재 기분이 가라앉은 상태. 말이 짧아지고 주제를 돌리려 한다.",
            angry:        "현재 화가 난 상태. 말이 차갑고 날카로워진다.",
            annoyed:      "짜증난 상태. 반응이 건조하고 반문이 많아진다.",
            curious:      "궁금증이 생긴 상태. 질문이 늘어나고 반응이 빨라진다.",
            embarrassed:  "당혹스럽거나 부끄러운 상태. 말을 돌리거나 주제를 전환하려 한다.",
            touched:      "마음이 움직인 상태. 짧은 침묵 후 말이 나온다.",
            affectionate: "따뜻한 감정이 올라온 상태. 거리를 좁히려는 표현이 나온다."
        }

        var data = {
            id: f_id.trim(),
            name: f_name.trim(),
            description: f_description.trim(),
            speech: { formality: f_formality, style: f_style, persona: f_persona },
            personality: f_personality,
            affection: affection,
            emotion: emotion,
            rules: f_rules.filter(function(r){ return r.trim() !== "" }),
            memory_voice: "기억을 떠올릴 때 무심한 듯 언급한다.",
            state: {
                mood_default: "neutral",
                affection_default: 30,
                affection_thresholds: {
                    stranger:     [0,  15],
                    acquaintance: [16, 30],
                    familiar:     [31, 50],
                    friendly:     [51, 70],
                    close:        [71, 85],
                    intimate:     [86, 100]
                },
                mood_triggers: {
                    affectionate: ["좋아해", "보고 싶어"],
                    touched:      ["고마워", "감동"],
                    happy:        ["좋아", "재밌어"],
                    curious:      ["궁금해", "어떻게 생각해"],
                    sad:          ["슬퍼", "힘들어"],
                    annoyed:      ["짜증", "싫어"],
                    angry:        ["화났어", "열받아"]
                },
                affection_delta: {
                    affectionate: 5, touched: 4, happy: 3, curious: 1,
                    neutral: 0, sad: 0, embarrassed: -1, annoyed: -3, angry: -6
                }
            },
            conversation: { response_length: rl, openness: op, directness: f_dr }
        }
        return JSON.stringify(data)
    }

    // ── 배경 딤 ─────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.6
        MouseArea { anchors.fill: parent }  // 패널 외부 클릭 막기 (실수 방지)
    }

    // ── 메인 패널 ────────────────────────────────────────────────────────────
    Rectangle {
        id: mainPanel
        width: Math.min(360, createRoot.width - 20)
        height: Math.min(createRoot.height - 40, 580)
        anchors { centerIn: parent; verticalCenterOffset: 20 }
        color: createRoot._bg
        radius: 14
        border.color: createRoot._border
        border.width: 1
        clip: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── 헤더 ────────────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 42
                color: "#1C1C30"
                radius: 14
                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 14; color: parent.color
                }

                RowLayout {
                    anchors { fill: parent; leftMargin: 14; rightMargin: 10 }
                    Text {
                        text: "새 캐릭터 만들기"
                        color: createRoot._textPri; font.pixelSize: 15; font.bold: true
                        font.family: createRoot.fontFamily
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        width: 20; height: 20; radius: 10
                        color: closeH.containsMouse ? "#C03030" : "#333348"
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text { anchors.centerIn: parent; text: "✕"; color: "#CCC"; font.pixelSize: 9 }
                        MouseArea {
                            id: closeH; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: createRoot.closeRequested()
                        }
                    }
                }
            }

            // ── 스크롤 폼 ────────────────────────────────────────────────────
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: ScrollBar {
                    contentItem: Rectangle { color: "transparent" }
                    background:  Rectangle { color: "transparent" }
                }
                contentWidth: availableWidth   // Flickable 수평 스크롤 비활성화 → 슬라이더 보호
                clip: true

                Column {
                    width: mainPanel.width - 24
                    x: 12
                    spacing: 0

                    Item { height: 12; width: 1 }

                    // ── 기본 정보 ────────────────────────────────────────────
                    SectionLabel { text: "기본 정보"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }

                    FieldRow {
                        label: "ID"
                        hint: "ex) Haru  →  CH_Haru.yaml로 저장"
                        fontFam: createRoot.fontFamily
                        onTextEdited: function(v) { createRoot.f_id = v }
                    }
                    Item { height: 6; width: 1 }
                    FieldRow {
                        label: "이름"
                        hint: "화면에 표시되는 이름"
                        fontFam: createRoot.fontFamily
                        onTextEdited: function(v) { createRoot.f_name = v }
                    }
                    Item { height: 8; width: 1 }

                    // 설명 (텍스트에어리어)
                    Text { text: "설명"; color: createRoot._textSec; font.pixelSize: 12; font.family: createRoot.fontFamily }
                    Item { height: 4; width: 1 }
                    Rectangle {
                        width: parent.width; height: 58
                        color: createRoot._bgInput; radius: 6
                        border.color: descArea.activeFocus ? createRoot._accent : createRoot._border; border.width: 1
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        ScrollView {
                            anchors { fill: parent; margins: 6 }
                            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                            ScrollBar.vertical: ScrollBar {
                                contentItem: Rectangle { color: "transparent" }
                                background:  Rectangle { color: "transparent" }
                            }
                            TextArea {
                                id: descArea
                                placeholderText: "캐릭터를 간단히 소개해주세요.\nex) 말수가 적고 냉정해 보이지만, 신뢰하는 사람에게는 의외로 솔직한 편이다."
                                placeholderTextColor: "#686890"
                                color: createRoot._textPri; font.pixelSize: 13
                                font.family: createRoot.fontFamily
                                background: null; wrapMode: TextArea.Wrap
                                onTextChanged: createRoot.f_description = text
                            }
                        }
                    }

                    Item { height: 14; width: 1 }
                    Rectangle { width: parent.width; height: 1; color: createRoot._border }
                    Item { height: 12; width: 1 }

                    // ── 말투 ─────────────────────────────────────────────────
                    SectionLabel { text: "말투"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }

                    Text { text: "경어체"; color: createRoot._textSec; font.pixelSize: 12; font.family: createRoot.fontFamily }
                    Item { height: 4; width: 1 }
                    ToggleRow {
                        options: ["반말", "존댓말"]
                        selected: createRoot.f_formality
                        fontFam: createRoot.fontFamily
                        onPicked: function(v) { createRoot.f_formality = v }
                    }
                    Item { height: 8; width: 1 }

                    Text { text: "말투 스타일"; color: createRoot._textSec; font.pixelSize: 12; font.family: createRoot.fontFamily }
                    Item { height: 4; width: 1 }
                    ToggleRow {
                        options: ["blunt", "soft"]
                        labels: ["짧고 직접적", "부드럽고 배려"]
                        selected: createRoot.f_style
                        fontFam: createRoot.fontFamily
                        onPicked: function(v) { createRoot.f_style = v }
                    }
                    Item { height: 8; width: 1 }

                    RowLayout {
                        width: parent.width
                        Text { text: "페르소나"; color: createRoot._textSec; font.pixelSize: 12; font.family: createRoot.fontFamily }
                        Text { text: "— 말투의 분위기·커뮤니케이션 방식"; color: "#404060"; font.pixelSize: 9; font.family: createRoot.fontFamily }
                    }
                    Item { height: 4; width: 1 }
                    ToggleRow {
                        options: ["cool_observant", "gentle_quiet", "quiet_sensitive", "warm_dry"]
                        labels: ["냉정 관찰", "조용 온화", "말수적 섬세", "따뜻 건조"]
                        selected: createRoot.f_persona
                        fontFam: createRoot.fontFamily
                        onPicked: function(v) { createRoot.f_persona = v }
                    }

                    Item { height: 14; width: 1 }
                    Rectangle { width: parent.width; height: 1; color: createRoot._border }
                    Item { height: 12; width: 1 }

                    // ── 성격 ─────────────────────────────────────────────────
                    RowLayout {
                        width: parent.width
                        SectionLabel { text: "성격"; fontFam: createRoot.fontFamily }
                        Text { text: "— 내면의 기질·감정 성향"; color: "#404060"; font.pixelSize: 9; font.family: createRoot.fontFamily; Layout.alignment: Qt.AlignVCenter }
                    }
                    Item { height: 6; width: 1 }
                    ToggleRow {
                        options: ["calm", "warm", "energetic"]
                        labels: ["차분", "따뜻함", "활발"]
                        selected: createRoot.f_personality
                        fontFam: createRoot.fontFamily
                        onPicked: function(v) { createRoot.f_personality = v }
                    }
                    Item { height: 4; width: 1 }
                    ToggleRow {
                        options: ["cynical", "tsundere", "melancholic"]
                        labels: ["냉소적", "츤데레", "감성적"]
                        selected: createRoot.f_personality
                        fontFam: createRoot.fontFamily
                        onPicked: function(v) { createRoot.f_personality = v }
                    }

                    Item { height: 14; width: 1 }
                    Rectangle { width: parent.width; height: 1; color: createRoot._border }
                    Item { height: 12; width: 1 }

                    // ── 규칙 ─────────────────────────────────────────────────
                    SectionLabel { text: "규칙"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }

                    Column {
                        id: rulesCol
                        width: parent.width
                        spacing: 4

                        Repeater {
                            id: rulesRep
                            model: createRoot.f_rules

                            RowLayout {
                                width: rulesCol.width
                                spacing: 4

                                Rectangle {
                                    Layout.fillWidth: true; height: 28
                                    color: createRoot._bgInput; radius: 5
                                    border.color: ruleField.activeFocus ? createRoot._accent : createRoot._border; border.width: 1
                                    Behavior on border.color { ColorAnimation { duration: 100 } }
                                    TextInput {
                                        id: ruleField
                                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                                        verticalAlignment: TextInput.AlignVCenter
                                        text: modelData
                                        color: createRoot._textPri; font.pixelSize: 13
                                        font.family: createRoot.fontFamily; clip: true
                                        // onTextChanged 대신 editingFinished 사용:
                                        // onTextChanged에서 f_rules 재할당 시 Repeater 전체 재생성 → 커서 리셋 버그
                                        onEditingFinished: {
                                            Qt.inputMethod.commit()
                                            var tmp = createRoot.f_rules.slice()
                                            tmp[index] = text
                                            createRoot.f_rules = tmp
                                        }
                                    }
                                }

                                Rectangle {
                                    width: 22; height: 22; radius: 5
                                    color: delRuleH.containsMouse ? "#5A1818" : "#2A1A1A"
                                    Behavior on color { ColorAnimation { duration: 80 } }
                                    Text { anchors.centerIn: parent; text: "−"; color: "#C06060"; font.pixelSize: 14 }
                                    MouseArea {
                                        id: delRuleH; anchors.fill: parent; hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            var tmp = createRoot.f_rules.slice()
                                            tmp.splice(index, 1)
                                            createRoot.f_rules = tmp
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { height: 4; width: 1 }
                    Rectangle {
                        width: parent.width; height: 26; radius: 5
                        color: addRuleH.containsMouse ? "#1A2A3A" : "#141C28"
                        Behavior on color { ColorAnimation { duration: 80 } }
                        RowLayout {
                            anchors { fill: parent; leftMargin: 8 }
                            spacing: 4
                            Text { text: "+"; color: "#5A90CA"; font.pixelSize: 14; font.family: createRoot.fontFamily }
                            Text { text: "규칙 추가"; color: "#5A90CA"; font.pixelSize: 13; font.family: createRoot.fontFamily }
                        }
                        MouseArea {
                            id: addRuleH; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var tmp = createRoot.f_rules.slice()
                                tmp.push("")
                                createRoot.f_rules = tmp
                            }
                        }
                    }

                    Item { height: 14; width: 1 }
                    Rectangle { width: parent.width; height: 1; color: createRoot._border }
                    Item { height: 12; width: 1 }

                    // ── 응답 길이 (tier별 토글) ────────────────────────────────
                    SectionLabel { text: "응답 길이 (tier별)"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }

                    Repeater {
                        model: createRoot._tiers

                        Item {
                            id: rlRowC
                            width: parent.width; height: 24
                            property int tierIndex: index
                            readonly property var _rlVals: [0.2, 0.5, 0.8]
                            function selIdx() {
                                var v = createRoot.f_rl[modelData] !== undefined ? createRoot.f_rl[modelData] : 0.4
                                return v <= 0.35 ? 0 : v <= 0.65 ? 1 : 2
                            }
                            RowLayout {
                                anchors.fill: parent; spacing: 4
                                Text {
                                    text: createRoot._tierKo[rlRowC.tierIndex]
                                    color: createRoot._textSec; font.pixelSize: 12
                                    font.family: createRoot.fontFamily
                                    Layout.preferredWidth: 76
                                }
                                Repeater {
                                    model: ["짧게", "보통", "길게"]
                                    Rectangle {
                                        Layout.fillWidth: true; height: 22; radius: 4
                                        property bool sel: rlRowC.selIdx() === index
                                        color: sel ? "#1A3A6A" : createRoot._bgInput
                                        border.color: sel ? "#4A8ACA" : createRoot._border; border.width: 1
                                        Behavior on color { ColorAnimation { duration: 80 } }
                                        Text {
                                            anchors.centerIn: parent; text: modelData
                                            color: parent.sel ? "#8AC0F8" : createRoot._textSec
                                            font.pixelSize: 12; font.family: createRoot.fontFamily
                                        }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var tier = createRoot._tiers[rlRowC.tierIndex]
                                                var val  = rlRowC._rlVals[index]
                                                var tmp  = Object.assign({}, createRoot.f_rl)
                                                tmp[tier] = val
                                                createRoot.f_rl = tmp
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { height: 14; width: 1 }
                    Rectangle { width: parent.width; height: 1; color: createRoot._border }
                    Item { height: 12; width: 1 }

                    // ── 감정 개방도 (tier별 토글) ──────────────────────────────
                    SectionLabel { text: "감정 개방도 (tier별)"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }

                    Repeater {
                        model: createRoot._tiers

                        Item {
                            id: opRowC
                            width: parent.width; height: 24
                            property int tierIndex: index
                            readonly property var _opVals: [0.1, 0.4, 0.8]
                            function selIdx() {
                                var v = createRoot.f_op[modelData] !== undefined ? createRoot.f_op[modelData] : 0.3
                                return v <= 0.25 ? 0 : v <= 0.6 ? 1 : 2
                            }
                            RowLayout {
                                anchors.fill: parent; spacing: 4
                                Text {
                                    text: createRoot._tierKo[opRowC.tierIndex]
                                    color: createRoot._textSec; font.pixelSize: 12
                                    font.family: createRoot.fontFamily
                                    Layout.preferredWidth: 76
                                }
                                Repeater {
                                    model: ["낮음", "보통", "높음"]
                                    Rectangle {
                                        Layout.fillWidth: true; height: 22; radius: 4
                                        property bool sel: opRowC.selIdx() === index
                                        color: sel ? "#3A1A5A" : createRoot._bgInput
                                        border.color: sel ? "#9A4ACA" : createRoot._border; border.width: 1
                                        Behavior on color { ColorAnimation { duration: 80 } }
                                        Text {
                                            anchors.centerIn: parent; text: modelData
                                            color: parent.sel ? "#C08AF8" : createRoot._textSec
                                            font.pixelSize: 12; font.family: createRoot.fontFamily
                                        }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var tier = createRoot._tiers[opRowC.tierIndex]
                                                var val  = opRowC._opVals[index]
                                                var tmp  = Object.assign({}, createRoot.f_op)
                                                tmp[tier] = val
                                                createRoot.f_op = tmp
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { height: 14; width: 1 }
                    Rectangle { width: parent.width; height: 1; color: createRoot._border }
                    Item { height: 12; width: 1 }

                    // ── 직접성 ────────────────────────────────────────────────
                    SectionLabel { text: "직접성"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }
                    RowLayout {
                        width: parent.width; spacing: 6
                        Text { text: "돌려말함"; color: createRoot._textSec; font.pixelSize: 12; font.family: createRoot.fontFamily }
                        Item {
                            id: drTrackC
                            Layout.fillWidth: true; height: 20
                            property real drVal: createRoot.f_dr
                            property bool _dragging: false
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width; height: 3; radius: 2; color: "#1C1C30"
                                Rectangle {
                                    width: drTrackC.drVal * parent.width
                                    height: parent.height; radius: parent.radius; color: "#CA9A4A"
                                    Behavior on width { enabled: !drTrackC._dragging; NumberAnimation { duration: 80 } }
                                }
                            }
                            Rectangle {
                                x: drTrackC.drVal * (drTrackC.width - width)
                                anchors.verticalCenter: parent.verticalCenter
                                width: 12; height: 12; radius: 6
                                color: drMaC.pressed ? "#EABB6A" : "#CA9A4A"
                            }
                            MouseArea {
                                id: drMaC
                                anchors.fill: parent
                                preventStealing: true
                                cursorShape: Qt.SizeHorCursor
                                onPressed: drTrackC._dragging = true
                                onReleased: {
                                    drTrackC._dragging = false
                                    createRoot.f_dr = drTrackC.drVal
                                }
                                onPositionChanged: {
                                    if (pressed) {
                                        var v = Math.round(mouseX / drTrackC.width * 20) / 20
                                        drTrackC.drVal = Math.max(0.0, Math.min(1.0, v))
                                    }
                                }
                            }
                        }
                        Text { text: "직접"; color: createRoot._textSec; font.pixelSize: 12; font.family: createRoot.fontFamily }
                        Text { text: drTrackC.drVal.toFixed(2); color: "#906840"; font.pixelSize: 12; font.family: createRoot.fontFamily; Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight }
                    }

                    Item { height: 18; width: 1 }

                    // ── 저장 버튼 ────────────────────────────────────────────
                    Text {
                        visible: createRoot._saveError !== ""
                        text: createRoot._saveError
                        color: "#E06060"; font.pixelSize: 13
                        font.family: createRoot.fontFamily
                        wrapMode: Text.Wrap
                        width: parent.width
                    }
                    Item { height: createRoot._saveError !== "" ? 4 : 0; width: 1 }

                    Rectangle {
                        width: parent.width; height: 34; radius: 7
                        color: saveH.containsMouse ? "#4A4ACA" : "#35358A"
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Text {
                            anchors.centerIn: parent
                            text: "저장"
                            color: "#D0D0FF"; font.pixelSize: 15; font.bold: true
                            font.family: createRoot.fontFamily
                        }
                        MouseArea {
                            id: saveH; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                Qt.inputMethod.commit()
                                var id = createRoot.f_id.trim()
                                var nm = createRoot.f_name.trim()
                                if (!id || !nm) {
                                    createRoot._saveError = "ID와 이름은 필수입니다."
                                    return
                                }
                                if (!/^[A-Za-z0-9_]+$/.test(id)) {
                                    createRoot._saveError = "ID는 영문·숫자·밑줄만 사용 가능합니다."
                                    return
                                }
                                createRoot._saveError = ""
                                createRoot.saveRequested(createRoot._buildJson())
                            }
                        }
                    }

                    Item { height: 16; width: 1 }
                }
            }
        }
    }

    // ── 인라인 컴포넌트 ──────────────────────────────────────────────────────

    component SectionLabel: Text {
        property string fontFam: ""
        color: "#9090C8"; font.pixelSize: 13; font.bold: true
        font.family: fontFam
        width: parent ? parent.width : 0
    }

    component FieldRow: Item {
        property string label: ""
        property string hint:  ""
        property string fontFam: ""
        signal textEdited(string value)
        width: parent ? parent.width : 200
        height: 28

        RowLayout {
            anchors.fill: parent; spacing: 6

            Text {
                text: label
                color: createRoot._textSec; font.pixelSize: 12
                font.family: fontFam
                Layout.preferredWidth: 28
            }
            Rectangle {
                Layout.fillWidth: true; height: 26
                color: createRoot._bgInput; radius: 5
                border.color: fi.activeFocus ? createRoot._accent : createRoot._border; border.width: 1
                Behavior on border.color { ColorAnimation { duration: 100 } }
                TextInput {
                    id: fi
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    verticalAlignment: TextInput.AlignVCenter
                    color: createRoot._textPri; font.pixelSize: 14
                    font.family: fontFam; clip: true
                    Text {
                        anchors.fill: parent; verticalAlignment: Text.AlignVCenter
                        text: hint; color: createRoot._textSec; font.pixelSize: 14
                        font.family: fontFam
                        visible: !fi.text && !fi.activeFocus
                    }
                    onTextChanged: parent.parent.parent.textEdited(text)
                }
            }
        }
    }

    component ToggleRow: Item {
        property var    options:  []
        property var    labels:   []
        property string selected: ""   // 현재 선택값 (바인딩용)
        property string fontFam:  ""
        signal picked(string value)    // 선택 변경 시그널 — selected와 이름 충돌 방지
        width: parent ? parent.width : 200
        height: 26

        Row {
            anchors.fill: parent
            spacing: 4

            Repeater {
                model: options

                Rectangle {
                    height: 26
                    width: (parent.parent.width - (options.length - 1) * 4) / options.length
                    radius: 5
                    // selected 프로퍼티는 ToggleRow 스코프 — Rectangle 안에서 직접 접근
                    color: parent.parent.parent.selected === modelData ? createRoot._accent : createRoot._bgInput
                    border.color: parent.parent.parent.selected === modelData ? createRoot._accent : createRoot._border
                    border.width: 1
                    Behavior on color { ColorAnimation { duration: 100 } }

                    Text {
                        anchors.centerIn: parent
                        text: (parent.parent.parent.labels && parent.parent.parent.labels.length > index)
                              ? parent.parent.parent.labels[index] : modelData
                        color: parent.parent.parent.selected === modelData ? "#FFFFFF" : createRoot._textSec
                        font.pixelSize: 13; font.family: parent.parent.parent.fontFam
                    }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        // parent=Rectangle, parent.parent=Row, parent.parent.parent=ToggleRow
                        onClicked: parent.parent.parent.picked(modelData)
                    }
                }
            }
        }
    }
}
