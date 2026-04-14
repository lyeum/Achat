import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 세계관 생성 패널 — 설정 > 세계관 > "세계관 생성" 버튼으로 열림
// culture / place / story 3개 섹션 각각 최대 4개 항목 입력
Item {
    id: wcRoot

    property string fontFamily: ""
    signal closeRequested()

    // ── 각 섹션 표시 항목 수 ──────────────────────────────────────────────────
    property int cultureCount: 1
    property int placeCount:   1
    property int storyCount:   1

    readonly property int maxItems: 4

    // ── 배경 딤 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent; color: "#000"; opacity: 0.55
        MouseArea {
            anchors.fill: parent
            onClicked: {
                var p = wcModal.mapFromItem(wcRoot, mouseX, mouseY)
                if (!wcModal.contains(p)) wcRoot.closeRequested()
            }
        }
    }

    // ── 모달 ─────────────────────────────────────────────────────────────────
    Rectangle {
        id: wcModal
        width: Math.min(500, wcRoot.width - 32)
        height: Math.min(wcRoot.height - 64, 680)
        anchors.centerIn: parent
        color: "#13131F"; radius: 12
        border.color: "#2A2A42"; border.width: 1

        // 헤더
        Rectangle {
            id: wcHeader
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 40; color: "#1A1A2E"; radius: 12
            Rectangle {
                anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                height: 12; color: parent.color
            }

            Text {
                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 14 }
                text: "세계관 생성"; color: "#C0C0E0"; font.pixelSize: 13; font.bold: true
                font.family: wcRoot.fontFamily
            }
            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 10 }
                width: 22; height: 22; radius: 11
                color: wcCloseHov.containsMouse ? "#C03030" : "#333348"
                Behavior on color { ColorAnimation { duration: 100 } }
                Text { anchors.centerIn: parent; text: "X"; color: "#CCC"; font.pixelSize: 10; font.bold: true }
                MouseArea { id: wcCloseHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: wcRoot.closeRequested() }
            }
        }

        // 스크롤 컨텐츠
        ScrollView {
            anchors { top: wcHeader.bottom; bottom: wcSaveBar.top; left: parent.left; right: parent.right }
            anchors.topMargin: 4; anchors.bottomMargin: 4
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            contentWidth: availableWidth

            Column {
                id: wcContent
                width: wcModal.width - 24
                x: 12; spacing: 0

                Item { height: 12; width: 1 }

                // ── world_id ────────────────────────────────────────────────
                Text { text: "세계관 ID"; color: "#7070A8"; font.pixelSize: 10; font.bold: true; font.family: wcRoot.fontFamily }
                Item { height: 4; width: 1 }
                Rectangle {
                    width: parent.width; height: 26; radius: 4; color: "#181828"; border.color: "#2A2A42"; border.width: 1; clip: true
                    TextInput {
                        id: wcWorldId; anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 6
                        color: "#E0E0E0"; font.pixelSize: 11; font.family: wcRoot.fontFamily
                    }
                    Text { anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 8 }
                        text: "ex) my_world"; color: "#505070"; font.pixelSize: 11; font.family: wcRoot.fontFamily
                        visible: wcWorldId.text.length === 0 && !wcWorldId.activeFocus }
                }

                Item { height: 16; width: 1 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { height: 12; width: 1 }

                // ── culture 섹션 ─────────────────────────────────────────────
                SectionBlock {
                    id: cultureBlock; width: wcContent.width
                    sectionLabel: "문화 (culture)"; sectionKey: "culture"
                    itemCount: wcRoot.cultureCount
                    fontFam: wcRoot.fontFamily
                    onAddItem: wcRoot.cultureCount = Math.min(wcRoot.cultureCount + 1, wcRoot.maxItems)
                }

                Item { height: 12; width: 1 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { height: 12; width: 1 }

                // ── place 섹션 ────────────────────────────────────────────────
                SectionBlock {
                    id: placeBlock; width: wcContent.width
                    sectionLabel: "장소 (place)"; sectionKey: "place"
                    itemCount: wcRoot.placeCount
                    fontFam: wcRoot.fontFamily
                    onAddItem: wcRoot.placeCount = Math.min(wcRoot.placeCount + 1, wcRoot.maxItems)
                }

                Item { height: 12; width: 1 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { height: 12; width: 1 }

                // ── story 섹션 ────────────────────────────────────────────────
                SectionBlock {
                    id: storyBlock; width: wcContent.width
                    sectionLabel: "스토리 (story)"; sectionKey: "story"
                    itemCount: wcRoot.storyCount
                    fontFam: wcRoot.fontFamily
                    onAddItem: wcRoot.storyCount = Math.min(wcRoot.storyCount + 1, wcRoot.maxItems)
                }

                Item { height: 12; width: 1 }
            }
        }

        // 저장 바
        Rectangle {
            id: wcSaveBar
            anchors { bottom: parent.bottom; left: parent.left; right: parent.right; bottomMargin: 0 }
            height: 50; color: "#0E0E1C"
            Rectangle {
                anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                height: 1; color: "#2A2A42"
            }

            Text {
                id: wcErrText
                anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 14 }
                color: "#E06060"; font.pixelSize: 10; font.family: wcRoot.fontFamily
                visible: text.length > 0
            }

            Rectangle {
                anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: 14 }
                width: 80; height: 30; radius: 6
                color: wcSaveHov.containsMouse ? "#4A4ACA" : "#35358A"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "저장"; color: "#D0D0FF"; font.pixelSize: 12; font.bold: true; font.family: wcRoot.fontFamily }
                MouseArea {
                    id: wcSaveHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        var wid = wcWorldId.text.trim()
                        if (!wid) { wcErrText.text = "세계관 ID를 입력하세요."; return }

                        var saved = 0
                        var blocks = [
                            { block: cultureBlock, sec: "culture", cnt: wcRoot.cultureCount },
                            { block: placeBlock,   sec: "place",   cnt: wcRoot.placeCount },
                            { block: storyBlock,   sec: "story",   cnt: wcRoot.storyCount }
                        ]
                        for (var b = 0; b < blocks.length; b++) {
                            var bl = blocks[b]
                            for (var i = 0; i < bl.cnt; i++) {
                                var item = bl.block.getItem(i)
                                if (item.title.trim() && item.content.trim()) {
                                    bridge.addWorldKnowledge(wid, bl.sec, item.title.trim(), item.content.trim(), item.trigger.trim())
                                    saved++
                                }
                            }
                        }

                        if (saved === 0) { wcErrText.text = "저장할 항목이 없습니다. 제목과 내용을 입력하세요."; return }
                        wcErrText.text = ""
                        wcRoot.closeRequested()
                    }
                }
            }
        }
    }

    // ── 섹션 블록 컴포넌트 ──────────────────────────────────────────────────
    component SectionBlock: Column {
        id: secBlock
        spacing: 6

        property string sectionLabel: ""
        property string sectionKey: ""
        property int    itemCount: 1
        property string fontFam: ""
        signal addItem()

        // 섹션 헤더
        RowLayout {
            width: parent.width
            Text { text: secBlock.sectionLabel; color: "#7070A8"; font.pixelSize: 10; font.bold: true; font.family: secBlock.fontFam; Layout.fillWidth: true }
            Rectangle {
                width: addSecLbl.implicitWidth + 14; height: 20; radius: 4
                color: addSecHov.containsMouse ? "#2A3A5A" : "#1A2A44"
                Behavior on color { ColorAnimation { duration: 100 } }
                visible: secBlock.itemCount < wcRoot.maxItems
                Text { id: addSecLbl; anchors.centerIn: parent; text: "+ 추가"; color: "#6090C0"; font.pixelSize: 9; font.family: secBlock.fontFam }
                MouseArea { id: addSecHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: secBlock.addItem() }
            }
        }

        // 항목 폼 (최대 maxItems)
        Repeater {
            model: wcRoot.maxItems
            delegate: ItemForm {
                id: itemFormInst
                width: secBlock.width
                formIndex: index
                visible: index < secBlock.itemCount
                height: visible ? implicitHeight : 0
                fontFam: secBlock.fontFam
            }
        }

        function getItem(i) {
            var rep = children[1]   // Repeater
            if (!rep) return { title: "", content: "", trigger: "" }
            var delegate = rep.itemAt(i)
            if (!delegate) return { title: "", content: "", trigger: "" }
            return { title: delegate.titleText, content: delegate.contentText, trigger: delegate.triggerText }
        }
    }

    // ── 항목 폼 컴포넌트 ────────────────────────────────────────────────────
    component ItemForm: Column {
        id: itemForm
        spacing: 4

        property int    formIndex: 0
        property string fontFam: ""
        property string titleText:   titleInput.text
        property string contentText: contentEdit.text
        property string triggerText: triggerInput.text

        // 구분선 (첫 항목 제외)
        Rectangle { width: parent.width; height: 1; color: "#1A1A32"; visible: formIndex > 0 }

        // 제목
        Rectangle {
            width: parent.width; height: 24; radius: 4; color: "#181828"; border.color: "#2A2A42"; border.width: 1; clip: true
            TextInput { id: titleInput; anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 6; color: "#E0E0E0"; font.pixelSize: 10; font.family: itemForm.fontFam }
            Text { anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 8 }
                text: "제목"; color: "#404060"; font.pixelSize: 10; font.family: itemForm.fontFam
                visible: titleInput.text.length === 0 && !titleInput.activeFocus }
        }

        // 내용
        Rectangle {
            width: parent.width; height: 72; radius: 4; color: "#181828"; border.color: "#2A2A42"; border.width: 1; clip: true
            Flickable {
                anchors.fill: parent; anchors.margins: 6
                contentWidth: width; contentHeight: contentEdit.implicitHeight
                clip: true; flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                TextEdit { id: contentEdit; width: parent.width; color: "#D0D0E8"; font.pixelSize: 10; font.family: itemForm.fontFam; wrapMode: TextEdit.Wrap; selectByMouse: true }
            }
            Text { anchors { left: parent.left; top: parent.top; leftMargin: 8; topMargin: 6 }
                text: "내용"; color: "#404060"; font.pixelSize: 10; font.family: itemForm.fontFam
                visible: contentEdit.text.length === 0 && !contentEdit.activeFocus }
        }

        // 트리거 키워드
        Rectangle {
            width: parent.width; height: 24; radius: 4; color: "#181828"; border.color: "#2A2A42"; border.width: 1; clip: true
            TextInput { id: triggerInput; anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 6; color: "#A0A0C0"; font.pixelSize: 10; font.family: itemForm.fontFam }
            Text { anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 8 }
                text: "트리거 키워드 (선택)  ex) 등대, 전설"; color: "#404060"; font.pixelSize: 10; font.family: itemForm.fontFam
                visible: triggerInput.text.length === 0 && !triggerInput.activeFocus }
        }
    }
}
