import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 관리자 패널 — 타이틀바 "관리" 버튼으로 열림
// 친밀도 / 감정 상태 / 직접성 즉시 조정
Item {
    id: adminRoot

    property string fontFamily:   ""
    property string convJson:     "{}"   // bridge.getConvParams() 결과
    property int    affection:    30     // bridge.currentAffection
    property bool   affLocked:    false  // bridge.affectionLocked
    property string currentMood:  "neutral"  // bridge.currentMood

    signal closeRequested()
    signal affectionSet(int value)
    signal affectionLocked(int value)
    signal affectionUnlocked()
    signal convParamChanged(string param, string tierOrKey, real value)
    signal moodSet(string mood)

    // ── 파싱 ─────────────────────────────────────────────────────────────────
    property var _conv: {
        try { return JSON.parse(adminRoot.convJson) }
        catch(e) { return {} }
    }

    readonly property var _moods: [
        { key: "neutral",      label: "기본"   },
        { key: "happy",        label: "행복"   },
        { key: "affectionate", label: "애정"   },
        { key: "touched",      label: "감동"   },
        { key: "curious",      label: "호기심" },
        { key: "sad",          label: "슬픔"   },
        { key: "embarrassed",  label: "당황"   },
        { key: "annoyed",      label: "짜증"   },
        { key: "angry",        label: "분노"   },
    ]

    // ── 배경 딤 ──────────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.5
        MouseArea {
            anchors.fill: parent
            onClicked: {
                var p = modal.mapFromItem(adminRoot, mouseX, mouseY)
                if (!modal.contains(p))
                    adminRoot.closeRequested()
            }
        }
    }

    // ── 모달 박스 ─────────────────────────────────────────────────────────────
    Rectangle {
        id: modal
        width: 290
        x: (adminRoot.width - width) / 2
        y: 48
        height: Math.min(headerRect.height + contentCol.implicitHeight + footerRect.height + 8,
                         adminRoot.height - 56)
        color: "#141420"
        radius: 12
        border.color: "#2A2A42"
        border.width: 1
        clip: true

        // ── 헤더 (드래그 핸들) ───────────────────────────────────────────────
        Rectangle {
            id: headerRect
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 38
            color: "#1C1C30"
            radius: 12
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }
            Text {
                anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }
                text: "관리자"
                color: "#C0C0E0"; font.pixelSize: 14; font.bold: true
                font.family: adminRoot.fontFamily
            }
            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                width: 20; height: 20; radius: 10
                color: closeHov.containsMouse ? "#C03030" : "#333348"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "X"; color: "#CCC"; font.pixelSize: 12; font.bold: true }
                MouseArea {
                    id: closeHov; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: adminRoot.closeRequested()
                }
            }
            MouseArea {
                anchors { left: parent.left; right: parent.right; leftMargin: 0; rightMargin: 32 }
                height: parent.height
                cursorShape: Qt.SizeAllCursor
                property point _start
                onPressed: _start = Qt.point(mouse.x, mouse.y)
                onPositionChanged: {
                    if (pressed) {
                        var dx = mouse.x - _start.x
                        var dy = mouse.y - _start.y
                        modal.x = Math.max(0, Math.min(modal.x + dx, adminRoot.width  - modal.width))
                        modal.y = Math.max(0, Math.min(modal.y + dy, adminRoot.height - modal.height))
                    }
                }
            }
        }

        // ── 스크롤 컨텐츠 ─────────────────────────────────────────────────────
        ScrollView {
            id: scrollView
            anchors {
                top: headerRect.bottom; bottom: footerRect.top
                left: parent.left; right: parent.right
                topMargin: 4; bottomMargin: 0
            }
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical: ScrollBar {
                contentItem: Rectangle { color: "transparent" }
                background:  Rectangle { color: "transparent" }
            }
            contentWidth: availableWidth

            Column {
                id: contentCol
                width: modal.width - 20
                x: 10
                spacing: 0

                // ── 친밀도 ────────────────────────────────────────────────────
                Item { width: 1; height: 10 }

                Text {
                    text: "친밀도"
                    color: "#7070A8"; font.pixelSize: 12; font.bold: true
                    font.family: adminRoot.fontFamily; leftPadding: 2
                }
                Item { width: 1; height: 6 }

                RowLayout {
                    width: parent.width; spacing: 8

                    Item {
                        id: affTrack
                        Layout.fillWidth: true; height: 22
                        opacity: adminRoot.affLocked ? 0.4 : 1.0
                        property real trackVal: adminRoot.affection / 100.0
                        property bool _dragging: false

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width; height: 4; radius: 2; color: "#252538"
                            Rectangle {
                                width: affTrack.trackVal * parent.width
                                height: parent.height; radius: parent.radius; color: "#5A5ACA"
                                Behavior on width { enabled: !affTrack._dragging; NumberAnimation { duration: 80 } }
                            }
                        }
                        Rectangle {
                            x: affTrack.trackVal * (affTrack.width - width)
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14; height: 14; radius: 7
                            color: affMa.pressed ? "#7A7AEA" : "#5A5ACA"
                            border.color: "#9090FF"; border.width: 1
                        }
                        MouseArea {
                            id: affMa
                            anchors.fill: parent; preventStealing: true
                            enabled: !adminRoot.affLocked
                            cursorShape: Qt.SizeHorCursor
                            onPressed:  affTrack._dragging = true
                            onReleased: {
                                affTrack._dragging = false
                                adminRoot.affectionSet(Math.round(affTrack.trackVal * 100))
                            }
                            onPositionChanged: {
                                if (pressed) {
                                    var v = Math.round(mouseX / affTrack.width * 100)
                                    affTrack.trackVal = Math.max(0, Math.min(1.0, v / 100.0))
                                }
                            }
                        }
                    }

                    Text {
                        text: Math.round(affTrack.trackVal * 100)
                        color: "#A0A0D0"; font.pixelSize: 14; font.bold: true
                        font.family: adminRoot.fontFamily
                        Layout.preferredWidth: 28; horizontalAlignment: Text.AlignRight
                    }
                }

                Item { width: 1; height: 12 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { width: 1; height: 10 }

                // ── 감정 상태 ─────────────────────────────────────────────────
                Text {
                    text: "감정 상태"
                    color: "#7070A8"; font.pixelSize: 12; font.bold: true
                    font.family: adminRoot.fontFamily; leftPadding: 2
                }
                Item { width: 1; height: 6 }

                Grid {
                    width: parent.width
                    columns: 3
                    spacing: 4

                    Repeater {
                        model: adminRoot._moods
                        Rectangle {
                            width: (contentCol.width - 8) / 3
                            height: 24; radius: 5
                            property bool sel: adminRoot.currentMood === modelData.key
                            color: sel ? "#2A3A6A" : (moodHov.containsMouse ? "#1E2A50" : "#1C1C30")
                            border.color: sel ? "#4A6ACA" : "#2A2A42"; border.width: 1
                            Behavior on color { ColorAnimation { duration: 80 } }
                            Text {
                                anchors.centerIn: parent; text: modelData.label
                                color: parent.sel ? "#8AAAF8" : "#505078"
                                font.pixelSize: 12; font.family: adminRoot.fontFamily
                            }
                            MouseArea {
                                id: moodHov; anchors.fill: parent
                                hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: adminRoot.moodSet(modelData.key)
                            }
                        }
                    }
                }

                Item { width: 1; height: 12 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { width: 1; height: 10 }

                // ── 직접성 ────────────────────────────────────────────────────
                Text {
                    text: "직접성"
                    color: "#7070A8"; font.pixelSize: 12; font.bold: true
                    font.family: adminRoot.fontFamily; leftPadding: 2
                }
                Item { width: 1; height: 6 }

                RowLayout {
                    width: parent.width; spacing: 6

                    Text {
                        text: "돌려말함"
                        color: "#606080"; font.pixelSize: 12; font.family: adminRoot.fontFamily
                    }

                    Item {
                        id: drTrack
                        Layout.fillWidth: true; height: 20
                        property real drVal: {
                            var dr = adminRoot._conv.directness
                            return (dr !== undefined) ? dr : 0.6
                        }
                        property bool _dragging: false

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width; height: 3; radius: 2; color: "#252538"
                            Rectangle {
                                width: drTrack.drVal * parent.width
                                height: parent.height; radius: parent.radius; color: "#CA9A4A"
                                Behavior on width { enabled: !drTrack._dragging; NumberAnimation { duration: 80 } }
                            }
                        }
                        Rectangle {
                            x: drTrack.drVal * (drTrack.width - width)
                            anchors.verticalCenter: parent.verticalCenter
                            width: 12; height: 12; radius: 6
                            color: drMa.pressed ? "#EABB6A" : "#CA9A4A"
                        }
                        MouseArea {
                            id: drMa
                            anchors.fill: parent; preventStealing: true
                            cursorShape: Qt.SizeHorCursor
                            onPressed: drTrack._dragging = true
                            onReleased: {
                                drTrack._dragging = false
                                adminRoot.convParamChanged("directness", "_", drTrack.drVal)
                            }
                            onPositionChanged: {
                                if (pressed) {
                                    var v = Math.round(mouseX / drTrack.width * 20) / 20
                                    drTrack.drVal = Math.max(0.0, Math.min(1.0, v))
                                }
                            }
                        }
                    }

                    Text {
                        text: "직접적"
                        color: "#606080"; font.pixelSize: 12; font.family: adminRoot.fontFamily
                    }

                    Text {
                        text: drTrack.drVal.toFixed(2)
                        color: "#9A8060"; font.pixelSize: 12; font.family: adminRoot.fontFamily
                        Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight
                    }
                }

                Item { width: 1; height: 10 }
            }
        }

        // ── 하단 고정 버튼 행 ─────────────────────────────────────────────────
        Rectangle {
            id: footerRect
            anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
            height: 44
            color: "#1C1C30"
            radius: 12
            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }

            RowLayout {
                anchors { fill: parent; leftMargin: 10; rightMargin: 10; topMargin: 8; bottomMargin: 8 }
                spacing: 6

                Rectangle {
                    Layout.fillWidth: true; height: 26; radius: 5
                    color: lockHov.containsMouse ? (adminRoot.affLocked ? "#6A2020" : "#206A30") : (adminRoot.affLocked ? "#3A1818" : "#183A20")
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        anchors.centerIn: parent
                        text: adminRoot.affLocked ? "잠금 해제" : "친밀도 잠금"
                        color: adminRoot.affLocked ? "#E06060" : "#60C080"
                        font.pixelSize: 13; font.family: adminRoot.fontFamily
                    }
                    MouseArea {
                        id: lockHov; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (adminRoot.affLocked) adminRoot.affectionUnlocked()
                            else adminRoot.affectionLocked(Math.round(affTrack.trackVal * 100))
                        }
                    }
                }

                Rectangle {
                    width: 60; height: 26; radius: 5
                    color: closeBtnHov.containsMouse ? "#2A2A50" : "#1E1E3A"
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Text {
                        anchors.centerIn: parent; text: "닫기"
                        color: "#8080B0"; font.pixelSize: 13; font.family: adminRoot.fontFamily
                    }
                    MouseArea {
                        id: closeBtnHov; anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: adminRoot.closeRequested()
                    }
                }
            }
        }
    }
}
