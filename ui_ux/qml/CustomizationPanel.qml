import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 커스터마이징 편집 패널 — 전체 오버레이 모달
//
// 슬롯 목록:
//   icon  — icons/{char_id}/{char_id}.png  (전신 아이콘)
//   base / hair / eye / mouth / cloth      (파츠 레이어)
//
// 이미지 등록 방법: 클릭 → 파일 브라우저 / 드래그&드롭
// 지원 형식: PNG(권장) · JPG · JPEG · WEBP · BMP · GIF · TIFF
Item {
    id: customRoot

    property string fontFamily:       ""
    property string partsJson:        "{}"   // 현재 parts.json 내용
    property string allPartsListJson: "{}"   // 미사용 (하위 호환 유지)

    signal closeRequested()
    signal saved(string partsJson)

    // ── 상태 ──────────────────────────────────────────────────────────────────
    property var    _editParts:   ({})
    property string _iconUrl:     ""
    property int    _iconVersion: 0   // 아이콘 캐시 무효화용 카운터

    Component.onCompleted: _resetState()
    onPartsJsonChanged:    _resetState()

    function _resetState() {
        try { _editParts = JSON.parse(customRoot.partsJson) } catch(e) { _editParts = {} }
        // 현재 아이콘 URL 로드
        try {
            var d = JSON.parse(bridge ? bridge.loadCustomization() : "{}")
            _iconUrl = d.icon_url || ""
        } catch(e) { _iconUrl = "" }
    }

    // 파츠 미리보기 URL (filename → file URL)
    function _partUrl(key) {
        var f = _editParts[key] || ""
        return f ? Qt.resolvedUrl("../assets/characters/" + key + "/" + f) : ""
    }

    // ── bridge 이미지 임포트 결과 수신 ───────────────────────────────────────
    Connections {
        target: bridge
        function onImageImported(slotType, result) {
            if (slotType === "icon") {
                customRoot._iconUrl     = result
                customRoot._iconVersion = customRoot._iconVersion + 1
            } else {
                var p = Object.assign({}, customRoot._editParts)
                p[slotType] = result
                customRoot._editParts = p
            }
        }
    }

    // ── 딤 배경 ───────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000"; opacity: 0.65
        MouseArea { anchors.fill: parent; onClicked: customRoot.closeRequested() }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panelRect
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
                    text: "캐릭터 커스터마이징"
                    color: "#E0E0E0"; font.pixelSize: 15; font.bold: true
                    font.family: customRoot.fontFamily
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
                        onClicked: customRoot.closeRequested()
                    }
                }
            }

            // 스크롤 본문
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: ScrollBar {
                    contentItem: Rectangle { color: "transparent" }
                    background:  Rectangle { color: "transparent" }
                }

                ColumnLayout {
                    width: panelRect.width - 20
                    x: 10
                    spacing: 12

                    Item { Layout.preferredHeight: 4 }

                    // ── 전신 아이콘 섹션 ─────────────────────────────────────
                    SectionHeader { label: "전신 아이콘"; fontFam: customRoot.fontFamily }

                    ImageSlot {
                        Layout.fillWidth: true
                        height: 160
                        slotType: "icon"
                        label: "아이콘 (icons/{캐릭터}/{캐릭터}.png)"
                        previewUrl: customRoot._iconUrl !== ""
                                    ? customRoot._iconUrl + "#v" + customRoot._iconVersion
                                    : ""
                        fontFam: customRoot.fontFamily
                    }

                    // ── 파츠 섹션 ────────────────────────────────────────────
                    SectionHeader { label: "파츠 레이어"; fontFam: customRoot.fontFamily }

                    // 2열 그리드
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 8
                        rowSpacing: 8

                        Repeater {
                            model: [
                                { key: "base",  label: "베이스 (얼굴/몸통)" },
                                { key: "hair",  label: "헤어"              },
                                { key: "eye",   label: "눈"                },
                                { key: "mouth", label: "입"                },
                                { key: "cloth", label: "의상"              },
                            ]
                            ImageSlot {
                                Layout.fillWidth: true
                                height: 130
                                slotType: modelData.key
                                label: modelData.label
                                previewUrl: customRoot._partUrl(modelData.key)
                                fontFam: customRoot.fontFamily
                                // parts도 교체 시 이미지 갱신 필요 → cache: false로 처리
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 6 }
                }
            }

            // 하단 저장 / 취소
            Rectangle {
                Layout.fillWidth: true
                height: 44; color: "#242424"; radius: 12
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
                        color: cancelHov.containsMouse ? "#3C3C3C" : "#2A2A2A"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent; text: "취소"
                            color: "#AAA"; font.pixelSize: 14; font.family: customRoot.fontFamily
                        }
                        MouseArea {
                            id: cancelHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: customRoot.closeRequested()
                        }
                    }

                    Rectangle {
                        width: 64; height: 28; radius: 6
                        color: saveHov.containsMouse ? "#357ABD" : "#4A90D9"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent; text: "저장"
                            color: "white"; font.pixelSize: 14; font.family: customRoot.fontFamily
                        }
                        MouseArea {
                            id: saveHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: customRoot.saved(JSON.stringify(customRoot._editParts))
                        }
                    }
                }
            }
        }
    }

    // ── 인라인 컴포넌트 ───────────────────────────────────────────────────────

    component SectionHeader: Text {
        property string label:   ""
        property string fontFam: ""
        Layout.fillWidth: true
        text: label
        color: "#4A90D9"; font.pixelSize: 14; font.bold: true
        font.family: fontFam
        leftPadding: 2
    }

    // 이미지 드롭존 슬롯
    component ImageSlot: Rectangle {
        id: slot
        property string slotType:   ""
        property string label:      ""
        property string previewUrl: ""
        property string fontFam:    ""

        radius: 8
        color:  dropZone.containsDrag ? "#1A3A6A"
                                      : (slotMa.containsMouse ? "#272727" : "#202020")
        border.color: dropZone.containsDrag ? "#4A90D9"
                                            : (slotMa.containsMouse ? "#555" : "#333")
        border.width: 1
        Behavior on color        { ColorAnimation { duration: 100 } }
        Behavior on border.color { ColorAnimation { duration: 100 } }

        // 이미지 미리보기
        Image {
            id: previewImg
            anchors {
                top: parent.top; left: parent.left; right: parent.right
                margins: 8; bottom: labelText.top; bottomMargin: 4
            }
            source: slot.previewUrl
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true; cache: false
            visible: slot.previewUrl !== "" && status === Image.Ready
        }

        // 플레이스홀더 (이미지 없을 때)
        Column {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -10
            visible: previewImg.source === "" || previewImg.status !== Image.Ready
            spacing: 6

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "＋"
                color: "#444"; font.pixelSize: 28
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "클릭 또는 드래그"
                color: "#444"; font.pixelSize: 12
                font.family: slot.fontFam
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "PNG · JPG · WEBP 등"
                color: "#333"; font.pixelSize: 9
                font.family: slot.fontFam
            }
        }

        // 슬롯 레이블
        Text {
            id: labelText
            anchors {
                bottom: parent.bottom; left: parent.left; right: parent.right
                bottomMargin: 6
            }
            text: slot.label
            color: "#666"; font.pixelSize: 12
            font.family: slot.fontFam
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            leftPadding: 4; rightPadding: 4
        }

        // 드래그&드롭
        DropArea {
            id: dropZone
            anchors.fill: parent
            onDropped: {
                if (drop.hasUrls && drop.urls.length > 0)
                    bridge.importImageFromDrop(slot.slotType, drop.urls[0].toString())
            }
        }

        // 클릭 → 파일 브라우저
        MouseArea {
            id: slotMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: bridge.browseImage(slot.slotType)
        }
    }
}
