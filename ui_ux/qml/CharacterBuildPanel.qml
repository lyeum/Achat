import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 캐릭터 커스텀 패널 — 픽크루 방식 파츠 선택
//
// 레이어 렌더 순서 (아래 → 위): base → eye → eyebrow → nose → mouth → hair → cloth
// 탭 순서는 UX 편의상 별도 유지.
// 3-열 스크롤 가능 그리드로 파츠 선택.
Item {
    id: cbRoot

    property string fontFamily:        ""
    property string partsJson:         "{}"
    property string allPartsListJson:  "{}"
    property string characterListJson: "[]"

    signal closeRequested()
    signal savedAsIcon(string charId, string partsJson)
    signal savedAsEmotion(string charId, string mood, string partsJson)

    // ── 탭 순서 (UX) ─────────────────────────────────────────────────────────
    readonly property var _categories: [
        { key: "base",    label: "베이스" },
        { key: "cloth",   label: "의상"   },
        { key: "hair",    label: "헤어"   },
        { key: "eye",     label: "눈"     },
        { key: "eyebrow", label: "눈썹"   },
        { key: "nose",    label: "코"     },
        { key: "mouth",   label: "입"     },
        { key: "emotion", label: "감정"   },
    ]

    // ── 렌더 순서 (프리뷰 레이어 합성): base → eye → eyebrow → nose → mouth → emotion → hair → cloth
    readonly property var _renderOrder: [
        "base", "eye", "eyebrow", "nose", "mouth", "emotion", "hair", "cloth"
    ]

    // ── 상태 ─────────────────────────────────────────────────────────────────
    property int _catIdx:         0
    property var _allParts:       ({})
    property var _editParts:      ({})
    property var _partIdxMap:     ({})
    property bool   _showCharPicker: false
    property string _pickerStep:    "char"   // "char" | "emotion"
    property string _pickerCharId:  ""

    on_ShowCharPickerChanged: { if (_showCharPicker) _pickerStep = "char" }

    property bool _partsInitialized: false  // 첫 로드 이후 외부 partsJson 변경 무시

    Component.onCompleted: _resetState()
    onPartsJsonChanged:    { if (!_partsInitialized) _resetState() }
    onAllPartsListJsonChanged: _resetState()
    on_CatIdxChanged: partsFlick.contentY = 0

    function _resetState() {
        try { _allParts  = JSON.parse(cbRoot.allPartsListJson) } catch(e) { _allParts  = {} }
        try { _editParts = JSON.parse(cbRoot.partsJson)        } catch(e) { _editParts = {} }

        var idxMap = {}
        var cats = cbRoot._categories
        for (var i = 0; i < cats.length; i++) {
            var key   = cats[i].key
            var parts = _allParts[key] || []
            var sel   = _editParts[key] || ""
            var idx   = sel ? parts.indexOf(sel) : -1
            idxMap[key] = idx >= 0 ? idx + 1 : 0
        }
        _partIdxMap = idxMap
        partsFlick.contentY = 0
        _partsInitialized = true   // 이후 외부 partsJson 변경은 무시
    }

    function _resetForClose() {
        _partsInitialized = false  // 다음 열기 때 다시 로드 허용
    }

    function _key()   { return _categories[_catIdx].key }
    function _parts() { return _allParts[_key()] || [] }

    function _partUrl(key, file) {
        if (!file) return ""
        return Qt.resolvedUrl("../assets/characters/" + key + "/" + file)
    }

    function _selectSlot(key, slotIdx) {
        var newIdxMap = Object.assign({}, _partIdxMap)
        newIdxMap[key] = slotIdx
        _partIdxMap = newIdxMap

        var newParts = Object.assign({}, _editParts)
        var parts = _allParts[key] || []
        newParts[key] = slotIdx === 0 ? "" : (parts[slotIdx - 1] || "")
        _editParts = newParts
    }

    // ── 딤 배경 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000"; opacity: 0.65
        MouseArea { anchors.fill: parent; onClicked: { cbRoot._resetForClose(); cbRoot.closeRequested() } }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: cbPanel
        anchors { fill: parent; margins: 10 }
        color: "#1A1A1A"
        radius: 12
        clip: true
        MouseArea { anchors.fill: parent; onClicked: {} }

        // ── 헤더 (40px) ──────────────────────────────────────────────────────
        Rectangle {
            id: cbHeader
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 40
            color: "#242424"; radius: 12
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }
            Text {
                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                text: "캐릭터 커스텀"
                color: "#E0E0E0"; font.pixelSize: 15; font.bold: true
                font.family: cbRoot.fontFamily
            }
            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                width: 20; height: 20; radius: 10
                color: cbXHov.containsMouse ? "#C03030" : "#444"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                MouseArea {
                    id: cbXHov; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { cbRoot._resetForClose(); cbRoot.closeRequested() }
                }
            }
        }

        // ── 하단 저장/취소 바 (44px) — 먼저 앵커 선언해야 나머지가 위에서 붙을 수 있음
        Rectangle {
            id: cbFooter
            anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
            height: 44
            color: "#242424"; radius: 12
            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }
            RowLayout {
                anchors { fill: parent; margins: 8 }
                spacing: 8
                Item { Layout.fillWidth: true }
                Rectangle {
                    width: 64; height: 28; radius: 6
                    color: cbCancelHov.containsMouse ? "#3C3C3C" : "#2A2A2A"
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text { anchors.centerIn: parent; text: "취소"; color: "#AAA"; font.pixelSize: 14; font.family: cbRoot.fontFamily }
                    MouseArea { id: cbCancelHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { cbRoot._resetForClose(); cbRoot.closeRequested() } }
                }
                Rectangle {
                    width: 64; height: 28; radius: 6
                    color: cbSaveHov.containsMouse ? "#357ABD" : "#4A90D9"
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text { anchors.centerIn: parent; text: "저장"; color: "white"; font.pixelSize: 14; font.family: cbRoot.fontFamily }
                    MouseArea { id: cbSaveHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: cbRoot._showCharPicker = true }
                }
            }
        }

        // ── 카테고리 탭 (36px) — 하단 바 바로 위
        Rectangle {
            id: cbTabs
            anchors { bottom: cbPartsArea.top; left: parent.left; right: parent.right }
            height: 36
            color: "#1E1E1E"

            Row {
                anchors.centerIn: parent
                spacing: 4

                Repeater {
                    model: cbRoot._categories
                    Rectangle {
                        width:  tabTxt.implicitWidth + 14
                        height: 26; radius: 6
                        color: cbRoot._catIdx === index
                               ? "#4A90D9"
                               : (tabHov.containsMouse ? "#2E2E2E" : "transparent")
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            id: tabTxt
                            anchors.centerIn: parent
                            text: modelData.label
                            color: cbRoot._catIdx === index ? "white" : "#AAA"
                            font.pixelSize: 13; font.family: cbRoot.fontFamily
                        }
                        MouseArea {
                            id: tabHov; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: cbRoot._catIdx = index
                        }
                    }
                }
            }
        }

        // ── 파츠 선택 영역 (40% of body) — 탭 아래, footer 위
        Rectangle {
            id: cbPartsArea
            anchors { bottom: cbFooter.top; left: parent.left; right: parent.right }
            // body = cbPanel.height - header(40) - tabs(36) - footer(44)
            // partsArea = body * 0.4
            height: (cbPanel.height - 40 - 36 - 44) * 0.4
            color: "#202020"
            clip: true

            // ── 스크롤 가능 그리드 ──────────────────────────────────────────
            Flickable {
                id: partsFlick
                anchors { fill: parent; margins: 6 }
                clip: true
                flickableDirection: Flickable.VerticalFlick
                contentHeight: partsGrid.implicitHeight
                contentWidth: width
                ScrollBar.vertical: ScrollBar {
                    policy: partsFlick.contentHeight > partsFlick.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                    width: 4
                
    contentItem: Rectangle { color: "transparent" }
    background: Rectangle { color: "transparent" }
}

                Grid {
                    id: partsGrid
                    width: partsFlick.width - (partsFlick.contentHeight > partsFlick.height ? 6 : 0)
                    columns: 3
                    spacing: 4

                    // 없음 슬롯
                    Rectangle {
                        property bool isSel: (cbRoot._partIdxMap[cbRoot._key()] || 0) === 0
                        width: (partsGrid.width - 8) / 3
                        height: width * 0.72
                        radius: 5
                        color: isSel ? "#1E3A6A" : (noneHov.containsMouse ? "#2A2A2A" : "#1E1E1E")
                        border.color: isSel ? "#4A90D9" : "#2A2A2A"; border.width: isSel ? 2 : 1
                        Behavior on color        { ColorAnimation { duration: 70 } }
                        Behavior on border.color { ColorAnimation { duration: 70 } }
                        Text {
                            anchors.centerIn: parent; text: "없음"
                            color: parent.isSel ? "#8AAAF8" : "#555"; font.pixelSize: 12
                            font.family: cbRoot.fontFamily
                        }
                        MouseArea {
                            id: noneHov; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: cbRoot._selectSlot(cbRoot._key(), 0)
                        }
                    }

                    // 실제 파츠 슬롯들
                    Repeater {
                        model: cbRoot._parts()
                        delegate: Rectangle {
                            id: partCell
                            property int slotIdx: index + 1
                            property bool isSel: (cbRoot._partIdxMap[cbRoot._key()] || 0) === slotIdx
                            property string cellFile: modelData

                            width: (partsGrid.width - 8) / 3
                            height: width * 0.72
                            radius: 5
                            color: isSel ? "#1E3A6A" : (pHov.containsMouse ? "#2A2A2A" : "#1E1E1E")
                            border.color: isSel ? "#4A90D9" : "#2A2A2A"; border.width: isSel ? 2 : 1
                            Behavior on color        { ColorAnimation { duration: 70 } }
                            Behavior on border.color { ColorAnimation { duration: 70 } }

                            Image {
                                id: cellImg
                                anchors { fill: parent; margins: 3 }
                                source: cbRoot._partUrl(cbRoot._key(), partCell.cellFile)
                                fillMode: Image.PreserveAspectFit
                                smooth: true; mipmap: true; cache: false
                                visible: source !== "" && status === Image.Ready
                            }

                            Text {
                                anchors.centerIn: parent
                                text: "?"
                                color: "#555"; font.pixelSize: 12
                                font.family: cbRoot.fontFamily
                                visible: !cellImg.visible
                            }

                            Text {
                                anchors { bottom: parent.bottom; left: parent.left; right: parent.right; bottomMargin: 1 }
                                text: partCell.cellFile.replace(/\.[^.]+$/, "")
                                color: partCell.isSel ? "#8AAAF8" : "#444"
                                font.pixelSize: 7; font.family: cbRoot.fontFamily
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight; leftPadding: 2; rightPadding: 2
                            }

                            MouseArea {
                                id: pHov; anchors.fill: parent; hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: cbRoot._selectSlot(cbRoot._key(), partCell.slotIdx)
                            }
                        }
                    }
                }
            }
        }

        // ── 프리뷰 영역 (60% of body) — 헤더 아래, 탭 위 ────────────────────
        Rectangle {
            id: cbPreview
            anchors { top: cbHeader.bottom; bottom: cbTabs.top; left: parent.left; right: parent.right }
            color: "#242424"
            clip: true

            property real _zoom: 1.0
            readonly property real _zoomMin: 1.0
            readonly property real _zoomMax: 4.0
            readonly property real _zoomStep: 0.5

            // ── 줌 가능한 뷰 ─────────────────────────────────────────────────
            Flickable {
                id: previewFlick
                anchors.fill: parent
                clip: true
                flickableDirection: Flickable.HorizontalAndVerticalFlick
                contentWidth:  Math.max(cbPreview.width,  cbPreview.width  * cbPreview._zoom)
                contentHeight: Math.max(cbPreview.height, cbPreview.height * cbPreview._zoom)
                // 줌 1.0일 때 스크롤 불필요 — 자동 중앙 정렬
                interactive: cbPreview._zoom > 1.0

                Item {
                    id: previewContent
                    width:  cbPreview.width  * cbPreview._zoom
                    height: cbPreview.height * cbPreview._zoom
                    // 줌 1.0일 때 중앙, 줌 아웃 불가이므로 항상 ≥ 컨테이너
                    x: Math.max(0, (previewFlick.width  - width)  / 2)
                    y: Math.max(0, (previewFlick.height - height) / 2)

                    // 렌더 순서: base → eye → eyebrow → nose → mouth → hair → cloth
                    Repeater {
                        model: cbRoot._renderOrder
                        Image {
                            anchors.fill: parent; anchors.margins: 6
                            source: cbRoot._partUrl(modelData,
                                                    cbRoot._editParts[modelData] || "")
                            fillMode: Image.PreserveAspectFit
                            smooth: true; mipmap: true; cache: false
                            visible: source !== "" && status === Image.Ready
                        }
                    }

                    // 아무 파츠도 없을 때 플레이스홀더
                    Text {
                        anchors.centerIn: parent
                        text: "😐"; font.pixelSize: 48
                        visible: {
                            var ep = cbRoot._editParts
                            for (var i = 0; i < cbRoot._categories.length; i++) {
                                if (ep[cbRoot._categories[i].key]) return false
                            }
                            return true
                        }
                    }
                }
            }

            // ── 줌 버튼 오버레이 (우하단) ────────────────────────────────────
            Row {
                anchors { right: parent.right; bottom: parent.bottom; margins: 6 }
                spacing: 3

                // 축소 버튼
                Rectangle {
                    width: 22; height: 22; radius: 5
                    color: zoomOutHov.containsMouse ? "#3A3A3A" : "#252525"
                    border.color: "#3A3A3A"; border.width: 1
                    opacity: cbPreview._zoom > cbPreview._zoomMin ? 1.0 : 0.35
                    Text { anchors.centerIn: parent; text: "−"; color: "#AAA"; font.pixelSize: 14; font.bold: true }
                    MouseArea {
                        id: zoomOutHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            cbPreview._zoom = Math.max(cbPreview._zoomMin,
                                                       cbPreview._zoom - cbPreview._zoomStep)
                            previewFlick.contentX = 0; previewFlick.contentY = 0
                        }
                    }
                }

                // 줌 표시 / 리셋 버튼
                Rectangle {
                    width: 36; height: 22; radius: 5
                    color: zoomResetHov.containsMouse ? "#3A3A3A" : "#252525"
                    border.color: "#3A3A3A"; border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: Math.round(cbPreview._zoom * 100) + "%"
                        color: "#888"; font.pixelSize: 9; font.family: cbRoot.fontFamily
                    }
                    MouseArea {
                        id: zoomResetHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            cbPreview._zoom = 1.0
                            previewFlick.contentX = 0; previewFlick.contentY = 0
                        }
                    }
                }

                // 확대 버튼
                Rectangle {
                    width: 22; height: 22; radius: 5
                    color: zoomInHov.containsMouse ? "#3A3A3A" : "#252525"
                    border.color: "#3A3A3A"; border.width: 1
                    opacity: cbPreview._zoom < cbPreview._zoomMax ? 1.0 : 0.35
                    Text { anchors.centerIn: parent; text: "+"; color: "#AAA"; font.pixelSize: 14; font.bold: true }
                    MouseArea {
                        id: zoomInHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            cbPreview._zoom = Math.min(cbPreview._zoomMax,
                                                       cbPreview._zoom + cbPreview._zoomStep)
                        }
                    }
                }
            }

            // 마우스 휠 줌
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                onWheel: {
                    if (wheel.angleDelta.y > 0)
                        cbPreview._zoom = Math.min(cbPreview._zoomMax, cbPreview._zoom + cbPreview._zoomStep)
                    else
                        cbPreview._zoom = Math.max(cbPreview._zoomMin, cbPreview._zoom - cbPreview._zoomStep)
                    if (cbPreview._zoom === cbPreview._zoomMin) {
                        previewFlick.contentX = 0; previewFlick.contentY = 0
                    }
                }
            }
        }

        // ── 캐릭터/저장 방식 선택 오버레이 ──────────────────────────────────
        Rectangle {
            anchors.fill: parent
            visible: cbRoot._showCharPicker
            color: "#CC000000"
            radius: 12
            z: 50

            MouseArea { anchors.fill: parent }

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 270)
                height: Math.min(340, parent.height - 40)
                radius: 10
                color: "#1A1A1A"
                border.color: "#3A3A3A"
                border.width: 1
                clip: true

                // ── 헤더 ─────────────────────────────────────────────────────
                Rectangle {
                    id: pkHeader
                    anchors { top: parent.top; left: parent.left; right: parent.right }
                    height: 44
                    color: "#242424"; radius: 10
                    Rectangle {
                        anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                        height: 10; color: parent.color
                    }
                    Text {
                        anchors.centerIn: parent
                        text: cbRoot._pickerStep === "char" ? "적용할 캐릭터 선택" : ("감정 선택 — " + cbRoot._pickerCharId)
                        color: "#E0E0E0"; font.pixelSize: 15; font.bold: true
                        font.family: cbRoot.fontFamily
                    }
                }

                // ── 하단 바 ───────────────────────────────────────────────────
                Rectangle {
                    id: pkFooter
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 44
                    color: "#242424"; radius: 10
                    Rectangle {
                        anchors { top: parent.top; left: parent.left; right: parent.right }
                        height: 10; color: parent.color
                    }
                    RowLayout {
                        anchors { fill: parent; margins: 8 }
                        spacing: 8
                        // 뒤로 (감정 선택 페이지에서만)
                        Rectangle {
                            visible: cbRoot._pickerStep === "emotion"
                            width: 60; height: 28; radius: 6
                            color: pkBackHov.containsMouse ? "#3C3C3C" : "#2A2A2A"
                            Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "← 뒤로"; color: "#AAA"; font.pixelSize: 14; font.family: cbRoot.fontFamily }
                            MouseArea { id: pkBackHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: cbRoot._pickerStep = "char" }
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            width: 60; height: 28; radius: 6
                            color: pkCancelHov.containsMouse ? "#3C3C3C" : "#2A2A2A"
                            Behavior on color { ColorAnimation { duration: 100 } }
                            Text { anchors.centerIn: parent; text: "취소"; color: "#AAA"; font.pixelSize: 14; font.family: cbRoot.fontFamily }
                            MouseArea { id: pkCancelHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: cbRoot._showCharPicker = false }
                        }
                    }
                }

                // ── [1단계] 캐릭터 + 저장 방식 선택 ─────────────────────────
                ListView {
                    anchors { top: pkHeader.bottom; left: parent.left; right: parent.right; bottom: pkFooter.top }
                    visible: cbRoot._pickerStep === "char"
                    clip: true
                    model: { try { return JSON.parse(cbRoot.characterListJson) } catch(e) { return [] } }
                    delegate: Item {
                        width: ListView.view.width
                        height: 38 + 34 + 34  // 이름(38) + 버튼2개(34×2)

                        // 캐릭터 이름 헤더
                        Rectangle {
                            id: charNameRow
                            anchors { top: parent.top; left: parent.left; right: parent.right }
                            height: 38
                            color: "#242424"
                            Text {
                                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 14 }
                                text: modelData.name || modelData.id
                                color: "#C8C8C8"; font.pixelSize: 15; font.bold: true
                                font.family: cbRoot.fontFamily
                            }
                        }

                        // 메인 아이콘 등록
                        Rectangle {
                            anchors { top: charNameRow.bottom; left: parent.left; right: parent.right }
                            height: 34
                            color: mainIconHov.containsMouse ? "#1E3A5A" : "transparent"
                            Behavior on color { ColorAnimation { duration: 70 } }
                            Text {
                                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 28 }
                                text: "▸  메인 아이콘 등록"
                                color: "#8AAAF8"; font.pixelSize: 14; font.family: cbRoot.fontFamily
                            }
                            MouseArea {
                                id: mainIconHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    cbRoot._showCharPicker = false
                                    cbRoot.savedAsIcon(modelData.id, JSON.stringify(cbRoot._editParts))
                                }
                            }
                        }

                        // 감정 표현 지정
                        Rectangle {
                            anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                            height: 34
                            color: emoPickHov.containsMouse ? "#1E3A5A" : "transparent"
                            Behavior on color { ColorAnimation { duration: 70 } }
                            Text {
                                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 28 }
                                text: "▸  감정 표현 지정"
                                color: "#8AAAF8"; font.pixelSize: 14; font.family: cbRoot.fontFamily
                            }
                            MouseArea {
                                id: emoPickHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    cbRoot._pickerCharId = modelData.id
                                    cbRoot._pickerStep = "emotion"
                                }
                            }
                        }

                        // 구분선
                        Rectangle {
                            anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                            height: 1; color: "#2A2A2A"
                        }
                    }
                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        contentItem: Rectangle { color: "transparent" }
                        background: Rectangle { color: "transparent" }
                    }
                }

                // ── [2단계] 감정 선택 (3×3 그리드) ──────────────────────────
                Grid {
                    anchors {
                        top: pkHeader.bottom; left: parent.left; right: parent.right
                        bottom: pkFooter.top; margins: 10
                    }
                    visible: cbRoot._pickerStep === "emotion"
                    columns: 3
                    spacing: 6

                    Repeater {
                        model: [
                            { key: "neutral",      label: "기본",   emoji: "😐" },
                            { key: "happy",        label: "행복",   emoji: "😊" },
                            { key: "affectionate", label: "애정",   emoji: "😍" },
                            { key: "touched",      label: "감동",   emoji: "😭" },
                            { key: "curious",      label: "호기심", emoji: "🤔" },
                            { key: "sad",          label: "슬픔",   emoji: "😢" },
                            { key: "embarrassed",  label: "당황",   emoji: "😳" },
                            { key: "annoyed",      label: "짜증",   emoji: "😤" },
                            { key: "angry",        label: "분노",   emoji: "😠" },
                        ]
                        Rectangle {
                            width: (parent.width - 12) / 3
                            height: width
                            radius: 6
                            color: emoMoodHov.containsMouse ? "#2A3A5A" : "#202020"
                            border.color: emoMoodHov.containsMouse ? "#4A90D9" : "#333"
                            border.width: 1
                            Behavior on color        { ColorAnimation { duration: 80 } }
                            Behavior on border.color { ColorAnimation { duration: 80 } }
                            Column {
                                anchors.centerIn: parent
                                spacing: 2
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.emoji; font.pixelSize: 22 }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.label; color: "#AAA"; font.pixelSize: 12; font.family: cbRoot.fontFamily }
                            }
                            MouseArea {
                                id: emoMoodHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var cid = cbRoot._pickerCharId
                                    cbRoot._showCharPicker = false
                                    cbRoot.savedAsEmotion(cid, modelData.key, JSON.stringify(cbRoot._editParts))
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
