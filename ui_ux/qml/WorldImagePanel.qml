import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 세계관 배경 이미지 관리 패널
// 설정 > 세계관 > "+ 세계관 이미지 추가" 버튼으로 열림
Item {
    id: root

    property string fontFamily: ""
    property string worldsJson: "[]"   // bridge.getWorldLocations() 결과

    signal closeRequested()

    // ── 배경 딤 ───────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.5
        MouseArea { anchors.fill: parent; onClicked: root.closeRequested() }
    }

    // ── 패널 본체 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: panel
        width: Math.min(400, root.width - 20)
        anchors {
            top: parent.top
            bottom: parent.bottom
            right: parent.right
        }
        color: "#1A1A1A"
        radius: 12

        // ── 헤더 ──────────────────────────────────────────────────────────────
        Rectangle {
            id: panelHeader
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 42
            color: "#242424"
            radius: 12
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }
            Text {
                anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
                text: "세계관 배경 이미지"
                color: "#E0E0E0"; font.pixelSize: 15; font.bold: true
                font.family: root.fontFamily
            }
            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                width: 22; height: 22; radius: 11
                color: closeHov.containsMouse ? "#C03030" : "#444"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "✕"; color: "white"; font.pixelSize: 9 }
                MouseArea {
                    id: closeHov; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.closeRequested()
                }
            }
        }

        // ── 안내 문구 ──────────────────────────────────────────────────────────
        Text {
            id: hintText
            anchors { top: panelHeader.bottom; topMargin: 8; left: parent.left; leftMargin: 12; right: parent.right; rightMargin: 12 }
            text: "장소별 배경 이미지를 지정합니다.\n이미지를 행에 드래그하거나 '파일 선택' 버튼을 클릭하세요."
            color: "#888"; font.pixelSize: 12; wrapMode: Text.Wrap
            font.family: root.fontFamily
        }

        // ── 스크롤 목록 ────────────────────────────────────────────────────────
        ScrollView {
            anchors {
                top: hintText.bottom; topMargin: 8
                bottom: parent.bottom; bottomMargin: 8
                left: parent.left; right: parent.right
            }
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical: ScrollBar {
                contentItem: Rectangle { color: "transparent" }
                background:  Rectangle { color: "transparent" }
            }

            Column {
                width: panel.width - 16
                x: 8
                spacing: 4

                Repeater {
                    model: {
                        try { return JSON.parse(root.worldsJson) }
                        catch(e) { return [] }
                    }

                    delegate: Column {
                        id: worldBlock
                        width: parent.width
                        spacing: 2

                        // 세계관 헤더 배지
                        Rectangle {
                            width: parent.width; height: 28
                            radius: 4; color: "#1E2A34"
                            Text {
                                anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                                text: "📁  " + modelData.world_id
                                color: "#7AAABB"; font.pixelSize: 13; font.bold: true
                                font.family: root.fontFamily
                            }
                        }

                        // 장소 목록
                        Repeater {
                            model: modelData.locations || []

                            delegate: Rectangle {
                                id: locRow
                                width: parent.width; height: 70
                                radius: 4
                                color: fullDrop.containsDrag ? "#1E2E3E"
                                     : (locHover.containsMouse ? "#252525" : "#1E1E1E")
                                border.color: fullDrop.containsDrag ? "#4A90D9" : "transparent"
                                border.width: 2
                                Behavior on color { ColorAnimation { duration: 100 } }

                                RowLayout {
                                    anchors { fill: parent; margins: 8 }
                                    spacing: 10

                                    // 이미지 미리보기 박스
                                    Rectangle {
                                        width: 50; height: 50; radius: 4
                                        color: "#111"; border.color: "#333"; border.width: 1

                                        Image {
                                            id: locPreview
                                            anchors { fill: parent; margins: 2 }
                                            source: modelData.image_url || ""
                                            fillMode: Image.PreserveAspectCrop
                                            visible: modelData.has_image && status === Image.Ready
                                            cache: false
                                        }

                                        Text {
                                            anchors.centerIn: parent
                                            text: "🖼"
                                            font.pixelSize: 20
                                            visible: !locPreview.visible
                                        }
                                    }

                                    // 이름 + 상태
                                    Column {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text {
                                            text: modelData.location
                                            color: "#D0D0D0"; font.pixelSize: 14; font.bold: true
                                            font.family: root.fontFamily
                                        }
                                        Text {
                                            text: modelData.has_image ? "✓ 이미지 있음" : "이미지 없음"
                                            color: modelData.has_image ? "#50C080" : "#777"
                                            font.pixelSize: 12; font.family: root.fontFamily
                                        }
                                    }

                                    // 파일 선택 버튼
                                    Rectangle {
                                        width: 76; height: 34; radius: 6
                                        color: browseHov.containsMouse ? "#357ABD" : "#2A4A6A"
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Text {
                                            anchors.centerIn: parent
                                            text: "파일 선택"
                                            color: "white"; font.pixelSize: 12
                                            font.family: root.fontFamily
                                        }
                                        MouseArea {
                                            id: browseHov; anchors.fill: parent
                                            hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                bridge.browseLocationImage(modelData.world_id, modelData.location)
                                            }
                                        }
                                    }
                                }

                                // 행 전체 드래그&드롭 영역
                                DropArea {
                                    id: fullDrop
                                    anchors.fill: parent
                                    keys: ["text/uri-list"]
                                    onDropped: function(drop) {
                                        if (drop.urls && drop.urls.length > 0) {
                                            bridge.importLocationImageFromDrop(
                                                modelData.world_id,
                                                modelData.location,
                                                drop.urls[0].toString()
                                            )
                                        }
                                    }
                                }

                                HoverHandler { id: locHover }

                                Rectangle {
                                    anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                                    height: 1; color: "#2A2A2A"
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }

                // 빈 상태 안내
                Item {
                    visible: {
                        try { return JSON.parse(root.worldsJson).length === 0 }
                        catch(e) { return true }
                    }
                    width: parent.width; height: 80
                    Text {
                        anchors.centerIn: parent
                        text: "등록된 세계관이 없습니다.\n설정 > 세계관 > 세계관 생성에서 먼저 세계관을 만들어 주세요."
                        color: "#555"; font.pixelSize: 13; wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                        font.family: root.fontFamily
                    }
                }
            }
        }
    }
}
