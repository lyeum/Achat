import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Window {
    id: root

    // ── 크기 / 상태 ─────────────────────────────────────────────────────────
    property bool   isBubble:          false   // false=풀창, true=PIP 모드
    property bool   pipBubbleOpen:     false   // PIP 말풍선 표시 여부
    property string currentMode:       "chat"  // "chat" | "function"
    property string currentTag:        ""      // 선택된 기능 태그 key (""=없음)
    property color  inputTagColor:     "#4A90D9" // 활성 태그 색상 → 입력창 테두리에 반영
    property string backgroundImageUrl: bridge ? bridge.currentBackground : ""
    property string currentMood:       bridge ? bridge.currentMood : "neutral"
    property bool   inputReady:        true    // 전송 가능 여부
    property bool   settingsOpen:      false   // 설정 패널 표시 여부
    property string charListJson:      "[]"    // getCharacterList() 캐시
    property string worldListJson:     "[]"    // getWorldList() 캐시

    // 커스터마이징
    property bool   emotionPanelOpen:      false
    property bool   characterBuildOpen:    false
    property bool   charSelectOpen:        false
    property bool   charStatusOpen:        false
    property bool   resetConfirmOpen:      false
    property string charStatusJson:        "{}"
    property string customPartsJson:       "{}"
    property string allPartsListJson:      "{}"

    // ── 테마 ──────────────────────────────────────────────────────────────────
    property string currentTheme: "ocean"

    readonly property var _themes: ({
        "ocean": {
            bgMain:         "#0E1C22",
            bgTitle:        "#142830",
            bgPanel:        "#122028",
            bgInput:        "#182C38",
            textPrimary:    "#A8D0D8",
            accent:         "#5A9EA8",
            tabInactive:    "#182830",
            bubbleAssist:   "#142830",
            tagBg:          "#101E28",
            tagBorder:      "#1E3C48",
            scrollbar:      "#2A5060",
            charBtnBg:      "#102030",
            charBtnHover:   "#183848",
            statusBtnBg:    "#101C28",
            statusBtnHover: "#183038"
        },
        "solar": {
            bgMain:         "#1C1610",
            bgTitle:        "#261E0C",
            bgPanel:        "#221A0E",
            bgInput:        "#2E2412",
            textPrimary:    "#D8C898",
            accent:         "#A07830",
            tabInactive:    "#2A2010",
            bubbleAssist:   "#261E0C",
            tagBg:          "#1E1810",
            tagBorder:      "#382C14",
            scrollbar:      "#503C18",
            charBtnBg:      "#281E0C",
            charBtnHover:   "#3A2C14",
            statusBtnBg:    "#221A0C",
            statusBtnHover: "#2E2410"
        },
        "forest": {
            bgMain:         "#101810",
            bgTitle:        "#141E14",
            bgPanel:        "#121C12",
            bgInput:        "#182418",
            textPrimary:    "#A8C8B0",
            accent:         "#5A8A68",
            tabInactive:    "#161E16",
            bubbleAssist:   "#141E14",
            tagBg:          "#101810",
            tagBorder:      "#1E3020",
            scrollbar:      "#2A4A30",
            charBtnBg:      "#101C12",
            charBtnHover:   "#182A1A",
            statusBtnBg:    "#101A12",
            statusBtnHover: "#162418"
        }
    })

    readonly property var _th: _themes[currentTheme] || _themes["ocean"]

    onCurrentThemeChanged: {
        if (currentTag === "") root.inputTagColor = _th.accent
    }

    // PIP 모드 진입 시 아이콘 하단 Y 좌표 보존 (말풍선이 위로 펼쳐지도록)
    property int pipAnchorY: 0

    // 창 크기: 풀창은 width 바인딩만 사용. height는 heightAnim이 직접 제어
    // (풀창↔PIP 전환 시 height 바인딩이 애니메이션에 의해 깨지는 문제 방지)
    width:  isBubble ? (pipBubbleOpen ? 280 : 160) : 432

    flags:  Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color:  "transparent"
    visible: true
    title:  "Achat"

    // 첫 렌더링 후 우하단 배치 (height는 바인딩 없이 명시적으로 초기화)
    Component.onCompleted: {
        root.height = 624
        x = Screen.width  - width  - 40
        y = Screen.height - height - 60
        _loadCustomization()
        if (bridge) root.currentTheme = bridge.getTheme()
    }

    function _loadCustomization() {
        if (!bridge) return
        try {
            var obj = JSON.parse(bridge.loadCustomization())
            customPartsJson = JSON.stringify(obj.parts || {})
        } catch(e) {}
    }

    // PIP 말풍선이 열릴 때 y/height를 동시에 변경해 아이콘 위치를 고정
    // (height Behavior와 y를 따로 움직이면 아이콘이 들떠 보이므로 명시적 애니메이션 사용)
    NumberAnimation { id: yAnim;      target: root; property: "y";      duration: 200; easing.type: Easing.InOutQuad }
    NumberAnimation { id: heightAnim; target: root; property: "height"; duration: 200; easing.type: Easing.InOutQuad }

    onPipBubbleOpenChanged: {
        if (!isBubble) return
        // PipWindow 내부 상태를 동기화 (외부에서 pipBubbleOpen을 바꾼 경우)
        if (pipView.bubbleOpen !== pipBubbleOpen) pipView.bubbleOpen = pipBubbleOpen

        if (pipBubbleOpen) {
            pipAnchorY = root.y + root.height   // 아이콘 하단 Y 저장 (열 때 1회)
            yAnim.to = pipAnchorY - 310; yAnim.start()
            heightAnim.to = 310;         heightAnim.start()
        } else {
            yAnim.to = pipAnchorY - 160; yAnim.start()
            heightAnim.to = 160;         heightAnim.start()
        }
    }

    // PIP ↔ 풀창 전환: height를 명시적으로 관리 (선언적 바인딩 제거로 애니메이션 충돌 방지)
    onIsBubbleChanged: {
        if (isBubble) {
            // 풀창 → PIP: 현재 bottom 위치 보존, 160px 아이콘으로 축소
            yAnim.stop(); heightAnim.stop()
            pipAnchorY = root.y + root.height
            pipBubbleOpen = false
            yAnim.to = pipAnchorY - 160; yAnim.start()
            heightAnim.to = 160;         heightAnim.start()
        } else {
            // PIP → 풀창: 애니메이션 중단 후 height/y 명시적 복원
            yAnim.stop(); heightAnim.stop()
            root.height = 624
            // 아이콘 bottom 기준으로 풀창을 위로 배치, 화면 밖으로 나가지 않게 클램프
            root.y = Math.min(Screen.height - 624 - 20, Math.max(0, pipAnchorY - 624))
        }
    }

    Behavior on width  { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }
    // height는 PIP 말풍선 전환 시 yAnim/heightAnim이 직접 제어하므로 Behavior 제거

    // taskbar X 또는 Alt+F4 → 앱 완전 종료
    onClosing: Qt.quit()

    // ── 전체 창 드래그 (OS 네이티브 — 버튼 이벤트 가로채지 않음) ─────────
    DragHandler {
        id: dragHandler
        target: null
        onActiveChanged: if (active) root.startSystemMove()
    }

    // ── hover 투명도 (HoverHandler — 이벤트 가로채지 않음) ────────────────
    HoverHandler { id: windowHover }
    opacity: windowHover.hovered || isBubble ? 1.0 : 0.85
    Behavior on opacity { NumberAnimation { duration: 300 } }

    // ── 한글 폰트 (Windows 폰트 경로에서 로드) ───────────────────────────
    FontLoader {
        id: koreanFont
        source: "file:///mnt/c/Windows/Fonts/malgun.ttf"
    }

    // ── 브리지 이벤트 수신 ───────────────────────────────────────────────
    Connections {
        target: bridge

        function onMessageAdded(role, content) {
            // assistant 응답 추가 전 thinking placeholder("...") 제거
            if (role === "assistant" && messageModel.count > 0) {
                var last = messageModel.get(messageModel.count - 1)
                if (last.content === "...") messageModel.remove(messageModel.count - 1)
            }
            messageModel.append({ "role": role, "content": content })
            Qt.callLater(() => { chatList.positionViewAtEnd() })
            // PIP 모드: assistant 응답이 오면 말풍선 자동 표시
            if (role === "assistant" && root.isBubble) {
                pipView.showBubble(content)
                root.pipBubbleOpen = true
            }
        }

        function onStatusChanged(status) {
            root.inputReady = (status === "ready")
            inputField.enabled = (status === "ready")
            if (status === "thinking") {
                messageModel.append({ "role": "assistant", "content": "..." })
            } else {
                if (messageModel.count > 0) {
                    var last = messageModel.get(messageModel.count - 1)
                    if (last.content === "...") messageModel.remove(messageModel.count - 1)
                }
            }
        }

        function onCharacterNameChanged(name) {
            // 바인딩 대신 직접 할당하지 않음 — charNameLabel.text 바인딩이 처리
        }

        function onBackgroundChanged(url) {
            root.backgroundImageUrl = url
        }

        function onMoodChanged(mood) {
            root.currentMood = mood
        }
    }

    // ── 메시지 모델 ──────────────────────────────────────────────────────
    ListModel { id: messageModel }

    // ── 메인 컨테이너 ────────────────────────────────────────────────────
    Rectangle {
        id: container
        anchors.fill: parent
        radius: root.isBubble ? 10 : 16
        color:  root.isBubble ? "transparent" : root._th.bgMain
        clip:   false

        Behavior on radius { NumberAnimation { duration: 200 } }
        Behavior on color  { ColorAnimation  { duration: 200 } }

        // ── PIP 마스코트 모드 ─────────────────────────────────────────────
        PipWindow {
            id: pipView
            visible: root.isBubble
            anchors.fill: parent
            fontFamily:   koreanFont.font.family
            currentMood:  root.currentMood
            characterId:  bridge ? bridge.characterId : ""
            inputEnabled: root.inputReady

            onBubbleOpenChanged: root.pipBubbleOpen = bubbleOpen

            onExpandRequested: {
                root.pipBubbleOpen = false
                root.isBubble = false
            }

            onMessageSent: function(text) {
                // bridge.sendMessage → messageAdded("user") emit → Connections.onMessageAdded가 처리
                // (직접 append 금지 — 중복 방지)
                bridge.sendMessage(text, root.currentMode)
            }
        }

        // ── 표정 / 아이콘 지정 패널 오버레이 ────────────────────────────
        EmotionPanel {
            anchors.fill: parent
            visible: root.emotionPanelOpen && !root.isBubble
            z: 20
            fontFamily:  koreanFont.font.family
            characterId: bridge ? bridge.characterId : ""
            onCloseRequested: root.emotionPanelOpen = false
        }

        // ── 캐릭터 커스텀 패널 오버레이 ──────────────────────────────────
        CharacterBuildPanel {
            anchors.fill: parent
            visible: root.characterBuildOpen && !root.isBubble
            z: 20
            fontFamily:       koreanFont.font.family
            partsJson:        root.customPartsJson
            allPartsListJson: root.allPartsListJson
            onCloseRequested: root.characterBuildOpen = false
            onSaved: function(pJson) {
                bridge.saveCustomization(JSON.stringify({ parts: JSON.parse(pJson) }))
                root.customPartsJson    = pJson
                root.characterBuildOpen = false
            }
        }

        // ── 설정 패널 오버레이 ────────────────────────────────────────────
        SettingsPanel {
            anchors.fill: parent
            visible: root.settingsOpen && !root.isBubble
            z: 10
            fontFamily:        koreanFont.font.family
            characterListJson: root.charListJson
            worldListJson:     root.worldListJson
            currentTheme:      root.currentTheme
            onCloseRequested: root.settingsOpen = false
            onThemeChangeRequested: function(themeId) {
                root.currentTheme = themeId
                if (bridge) bridge.saveTheme(themeId)
            }
            onEmotionPanelRequested: {
                root.emotionPanelOpen = true
            }
            onCharacterBuildRequested: {
                root.allPartsListJson   = bridge.getAllPartsList()
                root.customPartsJson    = bridge ? JSON.stringify(JSON.parse(bridge.loadCustomization()).parts || {}) : "{}"
                root.characterBuildOpen = true
            }
            onNewSessionRequested: function(keepMemory) {
                bridge.newSession(keepMemory)
            }
            onResetConfirmRequested: {
                root.settingsOpen    = false
                root.charListJson    = bridge.getCharacterList()
                root.resetConfirmOpen = true
            }
        }

        // ── 캐릭터 변경 패널 오버레이 ─────────────────────────────────────
        CharacterSelectPanel {
            anchors.fill: parent
            visible: root.charSelectOpen && !root.isBubble
            z: 20
            fontFamily:        koreanFont.font.family
            characterListJson: root.charListJson
            onCloseRequested:  root.charSelectOpen = false
            onCharacterChanged: function(charId) {
                bridge.changeCharacter(charId)
            }
            onAddRequested: {
                var newId = bridge.browseCharacterYaml()
                if (newId !== "") {
                    root.charListJson = bridge.getCharacterList()
                }
            }
        }

        // ── 캐릭터 상태 패널 오버레이 ─────────────────────────────────────
        CharacterStatusPanel {
            anchors.fill: parent
            visible: root.charStatusOpen && !root.isBubble
            z: 20
            fontFamily:  koreanFont.font.family
            statusJson:  root.charStatusJson
            onCloseRequested: root.charStatusOpen = false
        }

        // ── 캐릭터 초기화 확인 패널 오버레이 ─────────────────────────────
        ResetConfirmPanel {
            anchors.fill: parent
            visible: root.resetConfirmOpen && !root.isBubble
            z: 20
            fontFamily:        koreanFont.font.family
            characterListJson: root.charListJson
            onCloseRequested:  root.resetConfirmOpen = false
            onResetConfirmed: function(charId) {
                bridge.resetCharacter(charId)
                // 초기화 후 상태창 갱신
                if (root.charStatusOpen)
                    root.charStatusJson = bridge.getCharacterStatus()
            }
        }

        // ── 확장 모드 ────────────────────────────────────────────────────
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            visible: !root.isBubble

            // 타이틀바 (드래그 영역)
            Rectangle {
                id: titleBar
                Layout.fillWidth: true
                height: 38
                color: root._th.bgTitle
                radius: 16


                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 8 }

                    Text {
                        id: charNameLabel
                        text: bridge ? bridge.characterName : ""
                        color: root._th.textPrimary
                        font.pixelSize: 13
                        font.bold: true
                        font.family: koreanFont.font.family
                    }

                    // 캐릭터 변경 버튼
                    Rectangle {
                        width: 60; height: 20; radius: 4
                        color: charSelectBtnHov.containsMouse ? root._th.charBtnHover : root._th.charBtnBg
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text {
                            anchors.centerIn: parent; text: "캐릭터 변경"
                            color: root._th.accent; font.pixelSize: 10
                            font.family: koreanFont.font.family
                        }
                        MouseArea {
                            id: charSelectBtnHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.charListJson = bridge.getCharacterList()
                                root.charSelectOpen = true
                            }
                        }
                    }

                    // 상태 버튼
                    Rectangle {
                        width: 34; height: 20; radius: 4
                        color: charStatusBtnHov.containsMouse ? root._th.statusBtnHover : root._th.statusBtnBg
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text {
                            anchors.centerIn: parent; text: "상태"
                            color: root._th.accent; font.pixelSize: 10
                            font.family: koreanFont.font.family
                        }
                        MouseArea {
                            id: charStatusBtnHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.charStatusJson = bridge.getCharacterStatus()
                                root.charStatusOpen = true
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // 설정 버튼
                    Rectangle {
                        width: 20; height: 20; radius: 4
                        color: settingsHover.containsMouse ? "#3C3C3C" : "transparent"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text { anchors.centerIn: parent; text: "≡"; color: "#B0B0B0"; font.pixelSize: 13 }
                        MouseArea {
                            id: settingsHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.charListJson  = bridge.getCharacterList()
                                root.worldListJson = bridge.getWorldList()
                                root.settingsOpen  = true
                            }
                        }
                    }

                    // 버블 축소 버튼
                    Rectangle {
                        width: 20; height: 20; radius: 10
                        color: bubbleHover.containsMouse ? "#E09400" : "#F0A500"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text { anchors.centerIn: parent; text: "●"; color: "white"; font.pixelSize: 9 }
                        MouseArea {
                            id: bubbleHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.isBubble = true
                        }
                    }

                    // 닫기 버튼
                    Rectangle {
                        width: 20; height: 20; radius: 10
                        color: closeHover.containsMouse ? "#C03030" : "#E05050"
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                        MouseArea {
                            id: closeHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.quit()
                        }
                    }
                }
            }

            // 모드 전환 바
            Rectangle {
                Layout.fillWidth: true
                height: 32
                color: root._th.bgPanel

                RowLayout {
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    spacing: 6

                    Repeater {
                        model: [{ label: "대화", mode: "chat" }, { label: "기능", mode: "function" }]

                        Rectangle {
                            Layout.fillWidth: true
                            height: 22
                            radius: 6
                            color: root.currentMode === modelData.mode ? root._th.accent : root._th.tabInactive
                            Behavior on color { ColorAnimation { duration: 150 } }

                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                color: root.currentMode === modelData.mode ? "white" : "#888"
                                font.pixelSize: 13
                                font.family: koreanFont.font.family
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    root.currentMode = modelData.mode
                                    if (modelData.mode === "chat") {
                                        root.currentTag      = ""
                                        root.inputTagColor   = "#4A90D9"
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // 채팅 영역
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                // act별 배경 이미지 (이미지가 없으면 숨김 — 기존 다크 배경 유지)
                Image {
                    id: bgImage
                    anchors.fill: parent
                    source: root.backgroundImageUrl
                    fillMode: Image.PreserveAspectCrop
                    visible: root.backgroundImageUrl !== ""
                    opacity: 0.55
                    Behavior on opacity { NumberAnimation { duration: 400 } }
                }

                ListView {
                    id: chatList
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: parent.height - 120  // 캐릭터 아이콘 가시 영역(120px) 제외
                    clip: true
                    spacing: 4
                    bottomMargin: 8
                    topMargin: 8
                    leftMargin: 4
                    rightMargin: 4

                    model: messageModel

                    delegate: ChatBubble {
                        width: chatList.width - 8
                        role: model.role
                        content: model.content
                        fontFamily: koreanFont.font.family
                        userBubbleColor:   root._th.accent
                        assistBubbleColor: root._th.bubbleAssist
                    }

                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        contentItem: Rectangle {
                            implicitWidth: 4
                            radius: 2
                            color: root._th.scrollbar
                        }
                    }
                }

                // ── 기능 태그 pills (기능 모드일 때만 표시) ──────────────────
                // 대화 모드: 이 영역은 숨김 (차후 도트 애니메이션 예정)
                Item {
                    visible: root.currentMode === "function"
                    anchors {
                        left:   parent.left;  leftMargin:  140  // 캐릭터(128) + 간격(12)
                        right:  parent.right; rightMargin: 8
                        bottom: parent.bottom
                    }
                    height: 112
                    z: 1

                    Flow {
                        anchors { fill: parent; topMargin: 8 }
                        spacing: 6

                        Repeater {
                            model: [
                                { key: "image_convert",   label: "#이미지 변환",    color: "#4E7FB5" },
                                { key: "prompt_convert",  label: "#프롬프트 변환",  color: "#7A6BAA" },
                                { key: "file_rename",     label: "#파일 이름 변경", color: "#AA7840" },
                                { key: "folder_classify", label: "#폴더 분류",      color: "#3D8A72" },
                                { key: "local_search",    label: "#파일 검색",      color: "#6A8A3D" },
                                { key: "web_search",      label: "#웹 검색",        color: "#8A4A7A" },
                            ]

                            Rectangle {
                                property bool _active: root.currentTag === modelData.key
                                height: 24
                                width:  tagLabel.implicitWidth + 18
                                radius: 12

                                color: _active ? modelData.color : root._th.tagBg
                                border.color: _active ? modelData.color : root._th.tagBorder
                                border.width: 1
                                Behavior on color        { ColorAnimation { duration: 150 } }
                                Behavior on border.color { ColorAnimation { duration: 150 } }

                                Text {
                                    id: tagLabel
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    color: parent._active ? "white" : root._th.scrollbar
                                    font.pixelSize: 11
                                    font.family: koreanFont.font.family
                                    Behavior on color { ColorAnimation { duration: 150 } }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onEntered: if (!parent._active) parent.border.color = root._th.scrollbar
                                    onExited:  if (!parent._active) parent.border.color = root._th.tagBorder
                                    onClicked: {
                                        if (root.currentTag === modelData.key) {
                                            // 같은 태그 재클릭 → 해제
                                            root.currentTag    = ""
                                            root.currentMode   = "chat"
                                            root.inputTagColor = root._th.accent
                                        } else {
                                            root.currentTag    = modelData.key
                                            root.currentMode   = "function"
                                            root.inputTagColor = modelData.color
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // SD 캐릭터 — 입력창 테두리에 걸치는 형태
                // 하반신 40px가 아래 입력 영역에 의해 자연스럽게 가려짐
                CharacterDisplay {
                    id: charDisplay
                    z: 2
                    width: 128; height: 160
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: -40   // 40px 아래 입력창 영역으로 오버랩
                    x: 8
                    characterId: bridge ? bridge.characterId : ""
                    partsJson:   root.customPartsJson
                    currentMood: root.currentMood
                }
            }

            // 입력 영역
            Rectangle {
                Layout.fillWidth: true
                height: 48
                color: root._th.bgPanel
                radius: 16

                RowLayout {
                    anchors { fill: parent; leftMargin: 10; rightMargin: 10; topMargin: 6; bottomMargin: 6 }
                    spacing: 6

                    Rectangle {
                        Layout.fillWidth: true
                        height: 32
                        radius: 8
                        color: root._th.bgInput
                        border.color: inputField.activeFocus
                                      ? root.inputTagColor
                                      : (root.currentTag !== "" ? Qt.darker(root.inputTagColor, 1.5) : "#444")
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        TextInput {
                            id: inputField
                            anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                            verticalAlignment: TextInput.AlignVCenter
                            color: "#E0E0E0"
                            font.pixelSize: 13
                            font.family: koreanFont.font.family
                            clip: true

                            Text {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                text: "메시지 입력..."
                                color: "#555"
                                font: inputField.font
                                visible: inputField.text === "" && !inputField.activeFocus
                            }

                            Keys.onReturnPressed: sendMessage()
                        }
                    }

                    Rectangle {
                        width: 32; height: 32
                        radius: 8
                        color: root.inputReady
                               ? (sendBtnHover.containsMouse ? "#357ABD" : "#4A90D9")
                               : "#333"
                        Behavior on color { ColorAnimation { duration: 150 } }

                        Text {
                            id: sendBtn
                            anchors.centerIn: parent
                            text: root.inputReady ? "▶" : "…"
                            color: root.inputReady ? "white" : "#666"
                            font.pixelSize: 13
                        }

                        MouseArea {
                            id: sendBtnHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: root.inputReady ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: if (root.inputReady) sendMessage()
                        }
                    }
                }
            }
        }
    }

    // ── 메시지 전송 ─────────────────────────────────────────────────────────
    function sendMessage() {
        var text = inputField.text.trim()
        if (text === "") return
        inputField.text = ""
        bridge.sendMessage(text, root.currentMode)
    }
}
