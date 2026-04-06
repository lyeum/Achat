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
        var data = {
            id: f_id.trim(),
            name: f_name.trim(),
            description: f_description.trim(),
            speech: { formality: f_formality, style: f_style, persona: f_persona },
            personality: f_personality,
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
                        color: createRoot._textPri; font.pixelSize: 13; font.bold: true
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
                        hint: "영문+숫자, 파일명에 사용됨"
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
                    Text { text: "설명"; color: createRoot._textSec; font.pixelSize: 10; font.family: createRoot.fontFamily }
                    Item { height: 4; width: 1 }
                    Rectangle {
                        width: parent.width; height: 58
                        color: createRoot._bgInput; radius: 6
                        border.color: descArea.activeFocus ? createRoot._accent : createRoot._border; border.width: 1
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                        ScrollView {
                            anchors { fill: parent; margins: 6 }
                            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                            TextArea {
                                id: descArea
                                placeholderText: "캐릭터 외형/성격 개요..."
                                color: createRoot._textPri; font.pixelSize: 12
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

                    Text { text: "경어체"; color: createRoot._textSec; font.pixelSize: 10; font.family: createRoot.fontFamily }
                    Item { height: 4; width: 1 }
                    ToggleRow {
                        options: ["반말", "존댓말"]
                        selected: createRoot.f_formality
                        fontFam: createRoot.fontFamily
                        onPicked: function(v) { createRoot.f_formality = v }
                    }
                    Item { height: 8; width: 1 }

                    Text { text: "말투 스타일"; color: createRoot._textSec; font.pixelSize: 10; font.family: createRoot.fontFamily }
                    Item { height: 4; width: 1 }
                    ToggleRow {
                        options: ["blunt", "soft"]
                        labels: ["짧고 직접적", "부드럽고 배려"]
                        selected: createRoot.f_style
                        fontFam: createRoot.fontFamily
                        onPicked: function(v) { createRoot.f_style = v }
                    }
                    Item { height: 8; width: 1 }

                    Text { text: "페르소나"; color: createRoot._textSec; font.pixelSize: 10; font.family: createRoot.fontFamily }
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
                    SectionLabel { text: "성격"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }
                    ToggleRow {
                        options: ["calm", "cynical", "tsundere"]
                        labels: ["차분 안정", "냉소적", "츤데레"]
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
                                        color: createRoot._textPri; font.pixelSize: 11
                                        font.family: createRoot.fontFamily; clip: true
                                        // onTextChanged 대신 editingFinished 사용:
                                        // onTextChanged에서 f_rules 재할당 시 Repeater 전체 재생성 → 커서 리셋 버그
                                        onEditingFinished: {
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
                            Text { text: "규칙 추가"; color: "#5A90CA"; font.pixelSize: 11; font.family: createRoot.fontFamily }
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

                    // ── 응답 길이 슬라이더 ────────────────────────────────────
                    SectionLabel { text: "응답 길이 (tier별)"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }

                    Repeater {
                        model: createRoot._tiers

                        RowLayout {
                            width: parent.width
                            spacing: 6

                            Text {
                                text: createRoot._tierKo[index]
                                color: createRoot._textSec; font.pixelSize: 10
                                font.family: createRoot.fontFamily
                                Layout.preferredWidth: 72
                            }
                            Slider {
                                id: rlS
                                Layout.fillWidth: true
                                from: 0.0; to: 1.0; stepSize: 0.05
                                Component.onCompleted: value = (createRoot.f_rl[modelData] !== undefined ? createRoot.f_rl[modelData] : 0.4)
                                background: Rectangle {
                                    x: rlS.leftPadding; y: rlS.topPadding + rlS.availableHeight/2 - height/2
                                    width: rlS.availableWidth; height: 3; radius: 2; color: "#1C1C30"
                                    Rectangle { width: rlS.visualPosition * parent.width; height: parent.height; radius: parent.radius; color: "#4A8ACA" }
                                }
                                handle: Rectangle {
                                    x: rlS.leftPadding + rlS.visualPosition * (rlS.availableWidth - width)
                                    y: rlS.topPadding + rlS.availableHeight/2 - height/2
                                    width: 12; height: 12; radius: 6; color: "#4A8ACA"
                                }
                                onPressedChanged: {
                                    if (!pressed) {
                                        var tmp = Object.assign({}, createRoot.f_rl)
                                        tmp[modelData] = value
                                        createRoot.f_rl = tmp
                                    }
                                }
                            }
                            Text {
                                text: rlS.value.toFixed(2)
                                color: "#5080A0"; font.pixelSize: 10
                                font.family: createRoot.fontFamily
                                Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight
                            }
                        }
                    }

                    Item { height: 14; width: 1 }
                    Rectangle { width: parent.width; height: 1; color: createRoot._border }
                    Item { height: 12; width: 1 }

                    // ── 감정 개방도 슬라이더 ──────────────────────────────────
                    SectionLabel { text: "감정 개방도 (tier별)"; fontFam: createRoot.fontFamily }
                    Item { height: 6; width: 1 }

                    Repeater {
                        model: createRoot._tiers

                        RowLayout {
                            width: parent.width
                            spacing: 6

                            Text {
                                text: createRoot._tierKo[index]
                                color: createRoot._textSec; font.pixelSize: 10
                                font.family: createRoot.fontFamily
                                Layout.preferredWidth: 72
                            }
                            Slider {
                                id: opS
                                Layout.fillWidth: true
                                from: 0.0; to: 1.0; stepSize: 0.05
                                Component.onCompleted: value = (createRoot.f_op[modelData] !== undefined ? createRoot.f_op[modelData] : 0.3)
                                background: Rectangle {
                                    x: opS.leftPadding; y: opS.topPadding + opS.availableHeight/2 - height/2
                                    width: opS.availableWidth; height: 3; radius: 2; color: "#1C1C30"
                                    Rectangle { width: opS.visualPosition * parent.width; height: parent.height; radius: parent.radius; color: "#CA6A9A" }
                                }
                                handle: Rectangle {
                                    x: opS.leftPadding + opS.visualPosition * (opS.availableWidth - width)
                                    y: opS.topPadding + opS.availableHeight/2 - height/2
                                    width: 12; height: 12; radius: 6; color: "#CA6A9A"
                                }
                                onPressedChanged: {
                                    if (!pressed) {
                                        var tmp = Object.assign({}, createRoot.f_op)
                                        tmp[modelData] = value
                                        createRoot.f_op = tmp
                                    }
                                }
                            }
                            Text {
                                text: opS.value.toFixed(2)
                                color: "#905070"; font.pixelSize: 10
                                font.family: createRoot.fontFamily
                                Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight
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
                        Text { text: "돌려말함"; color: createRoot._textSec; font.pixelSize: 10; font.family: createRoot.fontFamily }
                        Slider {
                            id: drS
                            Layout.fillWidth: true
                            from: 0.0; to: 1.0; stepSize: 0.05
                            Component.onCompleted: value = createRoot.f_dr
                            background: Rectangle {
                                x: drS.leftPadding; y: drS.topPadding + drS.availableHeight/2 - height/2
                                width: drS.availableWidth; height: 3; radius: 2; color: "#1C1C30"
                                Rectangle { width: drS.visualPosition * parent.width; height: parent.height; radius: parent.radius; color: "#CA9A4A" }
                            }
                            handle: Rectangle {
                                x: drS.leftPadding + drS.visualPosition * (drS.availableWidth - width)
                                y: drS.topPadding + drS.availableHeight/2 - height/2
                                width: 12; height: 12; radius: 6; color: "#CA9A4A"
                            }
                            onPressedChanged: { if (!pressed) createRoot.f_dr = value }
                        }
                        Text { text: "직접"; color: createRoot._textSec; font.pixelSize: 10; font.family: createRoot.fontFamily }
                        Text { text: drS.value.toFixed(2); color: "#906840"; font.pixelSize: 10; font.family: createRoot.fontFamily; Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight }
                    }

                    Item { height: 18; width: 1 }

                    // ── 저장 버튼 ────────────────────────────────────────────
                    Text {
                        visible: createRoot._saveError !== ""
                        text: createRoot._saveError
                        color: "#E06060"; font.pixelSize: 11
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
                            color: "#D0D0FF"; font.pixelSize: 13; font.bold: true
                            font.family: createRoot.fontFamily
                        }
                        MouseArea {
                            id: saveH; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
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
        color: "#9090C8"; font.pixelSize: 11; font.bold: true
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
                color: createRoot._textSec; font.pixelSize: 10
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
                    color: createRoot._textPri; font.pixelSize: 12
                    font.family: fontFam; clip: true
                    Text {
                        anchors.fill: parent; verticalAlignment: Text.AlignVCenter
                        text: hint; color: createRoot._textSec; font.pixelSize: 12
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
                        font.pixelSize: 11; font.family: parent.parent.parent.fontFam
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
