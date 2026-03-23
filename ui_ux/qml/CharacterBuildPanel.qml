import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 캐릭터 커스텀 패널 — 픽크루 방식 파츠 선택
//
// 레이어 순서 (아래 → 위): base → cloth → hair → eye → eyebrow → mouth
// 각 카테고리 내 파츠를 ← → 버튼으로 순환 선택한다.
// 인덱스 0 = 없음(비어있음), 1.. = 실제 파츠
Item {
    id: cbRoot

    property string fontFamily:      ""
    property string partsJson:       "{}"  // 현재 저장된 파츠 선택
    property string allPartsListJson: "{}" // 카테고리별 파일 목록

    signal closeRequested()
    signal saved(string partsJson)

    // ── 카테고리 정의 (레이어 순서 = 프리뷰 합성 순서) ─────────────────────
    readonly property var _categories: [
        { key: "base",    label: "베이스" },
        { key: "cloth",   label: "의상"   },
        { key: "hair",    label: "헤어"   },
        { key: "eye",     label: "눈"     },
        { key: "eyebrow", label: "눈썹"   },
        { key: "mouth",   label: "입"     },
    ]

    // ── 상태 ─────────────────────────────────────────────────────────────────
    property int _catIdx:    0       // 현재 선택된 카테고리 탭
    property var _allParts:  ({})    // 파싱된 allPartsListJson
    property var _editParts: ({})    // 편집 중인 파츠 선택 (저장 전)
    property var _partIdxMap: ({})   // key → 현재 파츠 인덱스 (0=없음)

    Component.onCompleted: _resetState()
    onPartsJsonChanged:    _resetState()
    onAllPartsListJsonChanged: _resetState()

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
            idxMap[key] = idx >= 0 ? idx + 1 : 0  // 0=없음, 1..=파츠
        }
        _partIdxMap = idxMap
    }

    // ── 헬퍼 함수 ─────────────────────────────────────────────────────────────
    function _key()   { return _categories[_catIdx].key }
    function _parts() { return _allParts[_key()] || [] }
    function _total() { return _parts().length }  // 없음 포함하면 +1

    function _currentFile() {
        var idx = _partIdxMap[_key()] || 0
        return idx === 0 ? "" : (_parts()[idx - 1] || "")
    }

    function _partUrl(key, file) {
        if (!file) return ""
        return Qt.resolvedUrl("../assets/characters/" + key + "/" + file)
    }

    function _navigate(delta) {
        var key   = _key()
        var total = _parts().length + 1          // 0=없음 포함
        var idx   = ((_partIdxMap[key] || 0) + delta + total) % total

        var newIdxMap   = Object.assign({}, _partIdxMap)
        newIdxMap[key] = idx
        _partIdxMap = newIdxMap

        var newParts = Object.assign({}, _editParts)
        newParts[key] = idx === 0 ? "" : _parts()[idx - 1]
        _editParts = newParts
    }

    // ── 딤 배경 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000"; opacity: 0.65
        MouseArea { anchors.fill: parent; onClicked: cbRoot.closeRequested() }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: cbPanel
        anchors { fill: parent; margins: 10 }
        color: "#1A1A1A"
        radius: 12
        MouseArea { anchors.fill: parent; onClicked: {} }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── 헤더 ────────────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 40; color: "#242424"; radius: 12
                Rectangle {
                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                    height: 12; color: parent.color
                }
                Text {
                    anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                    text: "캐릭터 커스텀"
                    color: "#E0E0E0"; font.pixelSize: 13; font.bold: true
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
                        onClicked: cbRoot.closeRequested()
                    }
                }
            }

            // ── 프리뷰 영역 ─────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 220
                color: "#242424"
                // 프리뷰 레이어 합성 (base→cloth→hair→eye→eyebrow→mouth)
                Repeater {
                    model: cbRoot._categories
                    Image {
                        anchors.fill: parent
                        anchors.margins: 8
                        source: cbRoot._partUrl(modelData.key,
                                                cbRoot._editParts[modelData.key] || "")
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
                        var parts = cbRoot._editParts
                        var cats  = cbRoot._categories
                        for (var i = 0; i < cats.length; i++) {
                            if (parts[cats[i].key]) return false
                        }
                        return true
                    }
                }
            }

            // ── 카테고리 탭 ─────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 36
                color: "#1E1E1E"

                Row {
                    anchors.centerIn: parent
                    spacing: 4

                    Repeater {
                        model: cbRoot._categories
                        Rectangle {
                            width:  tabTxt.implicitWidth + 16
                            height: 28
                            radius: 6
                            color: cbRoot._catIdx === index
                                   ? "#4A90D9"
                                   : (tabHov.containsMouse ? "#2E2E2E" : "transparent")
                            Behavior on color { ColorAnimation { duration: 100 } }

                            Text {
                                id: tabTxt
                                anchors.centerIn: parent
                                text: modelData.label
                                color: cbRoot._catIdx === index ? "white" : "#AAA"
                                font.pixelSize: 12
                                font.family: cbRoot.fontFamily
                            }
                            MouseArea {
                                id: tabHov
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: cbRoot._catIdx = index
                            }
                        }
                    }
                }
            }

            // ── 파츠 선택기 ─────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#202020"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    // 카운터 (현재/전체)
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: {
                            var idx   = cbRoot._partIdxMap[cbRoot._key()] || 0
                            var total = cbRoot._total()
                            return idx === 0
                                ? "없음  (0 / " + total + ")"
                                : idx + " / " + total
                        }
                        color: "#888"; font.pixelSize: 11
                        font.family: cbRoot.fontFamily
                    }

                    // 파츠 프리뷰 + 화살표
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 8

                        // 이전 버튼
                        Rectangle {
                            width: 36; height: 36; radius: 8
                            color: prevHov.containsMouse ? "#3A3A3A" : "#2A2A2A"
                            Behavior on color { ColorAnimation { duration: 80 } }
                            Text { anchors.centerIn: parent; text: "◀"; color: "#AAA"; font.pixelSize: 14 }
                            MouseArea {
                                id: prevHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: cbRoot._navigate(-1)
                            }
                        }

                        // 파츠 이미지 프리뷰
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: "#2A2A2A"; radius: 8

                            Image {
                                id: partPreviewImg
                                anchors.fill: parent
                                anchors.margins: 6
                                source: cbRoot._partUrl(cbRoot._key(), cbRoot._currentFile())
                                fillMode: Image.PreserveAspectFit
                                smooth: true; mipmap: true; cache: false
                                visible: source !== "" && status === Image.Ready
                            }

                            // 없음 / 이미지 없음 플레이스홀더
                            Column {
                                anchors.centerIn: parent
                                spacing: 4
                                visible: !partPreviewImg.visible
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: cbRoot._currentFile() === "" ? "없음" : "?"
                                    color: "#555"; font.pixelSize: 16
                                    font.family: cbRoot.fontFamily
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: cbRoot._currentFile() === ""
                                          ? "파츠를 선택해주세요"
                                          : cbRoot._currentFile()
                                    color: "#444"; font.pixelSize: 10
                                    font.family: cbRoot.fontFamily
                                }
                            }

                            // 파일명 표시 (이미지가 있을 때)
                            Text {
                                anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 6 }
                                text: cbRoot._currentFile()
                                color: "#666"; font.pixelSize: 9
                                font.family: cbRoot.fontFamily
                                visible: partPreviewImg.visible
                            }
                        }

                        // 다음 버튼
                        Rectangle {
                            width: 36; height: 36; radius: 8
                            color: nextHov.containsMouse ? "#3A3A3A" : "#2A2A2A"
                            Behavior on color { ColorAnimation { duration: 80 } }
                            Text { anchors.centerIn: parent; text: "▶"; color: "#AAA"; font.pixelSize: 14 }
                            MouseArea {
                                id: nextHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: cbRoot._navigate(1)
                            }
                        }
                    }
                }
            }

            // ── 하단 저장 / 취소 ─────────────────────────────────────────────
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
                        color: cbCancelHov.containsMouse ? "#3C3C3C" : "#2A2A2A"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent; text: "취소"
                            color: "#AAA"; font.pixelSize: 12; font.family: cbRoot.fontFamily
                        }
                        MouseArea {
                            id: cbCancelHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: cbRoot.closeRequested()
                        }
                    }

                    Rectangle {
                        width: 64; height: 28; radius: 6
                        color: cbSaveHov.containsMouse ? "#357ABD" : "#4A90D9"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent; text: "저장"
                            color: "white"; font.pixelSize: 12; font.family: cbRoot.fontFamily
                        }
                        MouseArea {
                            id: cbSaveHov; anchors.fill: parent
                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: cbRoot.saved(JSON.stringify(cbRoot._editParts))
                        }
                    }
                }
            }
        }
    }
}
