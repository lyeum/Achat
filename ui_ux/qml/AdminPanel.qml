import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 관리자 패널 — 타이틀바 "관리" 버튼으로 열림
// 친밀도 직접 변경 / 대화 파라미터(response_length · openness · directness) 즉시 조정
Item {
    id: adminRoot

    property string fontFamily:   ""
    property string convJson:     "{}"   // bridge.getConvParams() 결과
    property int    affection:    30     // bridge.currentAffection
    property bool   affLocked:    false  // bridge.affectionLocked

    signal closeRequested()
    signal affectionSet(int value)
    signal affectionLocked(int value)
    signal affectionUnlocked()
    signal convParamChanged(string param, string tierOrKey, real value)

    // ── 파싱 ─────────────────────────────────────────────────────────────────
    property var _conv: {
        try { return JSON.parse(adminRoot.convJson) }
        catch(e) { return {} }
    }

    readonly property var _tiers: ["stranger", "acquaintance", "familiar", "friendly", "close", "intimate"]
    readonly property var _tierKo: ["낯선", "지인", "아는", "친한", "친밀", "신뢰"]

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
        // 드래그로 이동 가능 — 초기 위치는 상단 중앙
        x: (adminRoot.width - width) / 2
        y: 48
        height: Math.min(scrollView.contentHeight + headerRect.height + 8, adminRoot.height - 56)
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
                color: "#C0C0E0"; font.pixelSize: 12; font.bold: true
                font.family: adminRoot.fontFamily
            }
            Rectangle {
                anchors { verticalCenter: parent.verticalCenter; right: parent.right; rightMargin: 8 }
                width: 20; height: 20; radius: 10
                color: closeHov.containsMouse ? "#C03030" : "#333348"
                Behavior on color { ColorAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "X"; color: "#CCC"; font.pixelSize: 10; font.bold: true }
                MouseArea {
                    id: closeHov; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: adminRoot.closeRequested()
                }
            }
            // 헤더 드래그 → 모달 이동
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
                        var nx = modal.x + dx
                        var ny = modal.y + dy
                        modal.x = Math.max(0, Math.min(nx, adminRoot.width  - modal.width))
                        modal.y = Math.max(0, Math.min(ny, adminRoot.height - modal.height))
                    }
                }
            }
        }

        // ── 스크롤 컨텐츠 ─────────────────────────────────────────────────────
        ScrollView {
            id: scrollView
            anchors {
                top: headerRect.bottom; bottom: parent.bottom
                left: parent.left; right: parent.right
                topMargin: 4; bottomMargin: 4
            }
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            contentWidth: availableWidth  // Flickable 수평 스크롤 비활성화 → 슬라이더 이벤트 보호

            Column {
                id: contentCol
                width: modal.width - 20
                x: 10
                spacing: 0

                // ── 친밀도 섹션 ───────────────────────────────────────────────
                Item { width: 1; height: 10 }

                Text {
                    text: "친밀도"
                    color: "#7070A8"; font.pixelSize: 10; font.bold: true
                    font.family: adminRoot.fontFamily
                    leftPadding: 2
                }

                Item { width: 1; height: 6 }

                // 현재값 + 슬라이더
                RowLayout {
                    width: parent.width
                    spacing: 8

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
                            anchors.fill: parent
                            preventStealing: true
                            enabled: !adminRoot.affLocked
                            cursorShape: Qt.SizeHorCursor
                            onPressed:  affTrack._dragging = true
                            onReleased: affTrack._dragging = false
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
                        color: "#A0A0D0"; font.pixelSize: 12; font.bold: true
                        font.family: adminRoot.fontFamily
                        Layout.preferredWidth: 28
                        horizontalAlignment: Text.AlignRight
                    }
                }

                Item { width: 1; height: 4 }

                // 적용 / 잠금 버튼
                RowLayout {
                    width: parent.width
                    spacing: 6

                    Rectangle {
                        Layout.fillWidth: true; height: 24; radius: 5
                        color: applyHov.containsMouse ? "#3A3A80" : "#252548"
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text { anchors.centerIn: parent; text: "적용"; color: "#A0A0E0"; font.pixelSize: 11; font.family: adminRoot.fontFamily }
                        MouseArea {
                            id: applyHov; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: adminRoot.affectionSet(Math.round(affTrack.trackVal * 100))
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true; height: 24; radius: 5
                        color: lockHov.containsMouse ? (adminRoot.affLocked ? "#6A2020" : "#206A30") : (adminRoot.affLocked ? "#3A1818" : "#183A20")
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Text {
                            anchors.centerIn: parent
                            text: adminRoot.affLocked ? "[ 잠금 해제 ]" : "[ 잠금 ]"
                            color: adminRoot.affLocked ? "#E06060" : "#60C080"
                            font.pixelSize: 11; font.family: adminRoot.fontFamily
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
                }

                Item { width: 1; height: 14 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { width: 1; height: 12 }

                // ── 응답 길이 섹션 ────────────────────────────────────────────
                Text {
                    text: "응답 길이  (response_length)"
                    color: "#7070A8"; font.pixelSize: 10; font.bold: true
                    font.family: adminRoot.fontFamily
                }
                Item { width: 1; height: 6 }

                Repeater {
                    model: adminRoot._tiers

                    Item {
                        id: rlRow
                        width: contentCol.width; height: 24
                        property int tierIndex: index
                        property real curVal: {
                            var rl = adminRoot._conv.response_length
                            if (!rl) return 0.4
                            return (typeof rl === "object") ? (rl[modelData] !== undefined ? rl[modelData] : 0.4) : rl
                        }
                        function selIdx() { return curVal <= 0.35 ? 0 : curVal <= 0.65 ? 1 : 2 }
                        readonly property var _rlVals: [0.2, 0.5, 0.8]

                        RowLayout {
                            anchors.fill: parent; spacing: 4

                            Text {
                                text: adminRoot._tierKo[rlRow.tierIndex]
                                color: "#606080"; font.pixelSize: 10
                                font.family: adminRoot.fontFamily
                                Layout.preferredWidth: 36
                            }

                            Repeater {
                                model: ["짧게", "보통", "길게"]
                                Rectangle {
                                    Layout.fillWidth: true; height: 22; radius: 4
                                    property bool sel: rlRow.selIdx() === index
                                    color: sel ? "#2A4A7A" : "#1C1C30"
                                    border.color: sel ? "#4A8ACA" : "#2A2A42"; border.width: 1
                                    Behavior on color { ColorAnimation { duration: 80 } }
                                    Text {
                                        anchors.centerIn: parent; text: modelData
                                        color: parent.sel ? "#8AC0F8" : "#505078"
                                        font.pixelSize: 10; font.family: adminRoot.fontFamily
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            var tier = adminRoot._tiers[rlRow.tierIndex]
                                            var val  = rlRow._rlVals[index]
                                            adminRoot.convParamChanged("response_length", tier, val)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item { width: 1; height: 12 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { width: 1; height: 12 }

                // ── 감정 개방도 섹션 ──────────────────────────────────────────
                Text {
                    text: "감정 개방도  (openness)"
                    color: "#7070A8"; font.pixelSize: 10; font.bold: true
                    font.family: adminRoot.fontFamily
                }
                Item { width: 1; height: 6 }

                Repeater {
                    model: adminRoot._tiers

                    Item {
                        id: opRow
                        width: contentCol.width; height: 24
                        property int tierIndex: index
                        property real curVal: {
                            var op = adminRoot._conv.openness
                            if (!op) return 0.3
                            return (typeof op === "object") ? (op[modelData] !== undefined ? op[modelData] : 0.3) : op
                        }
                        function selIdx() { return curVal <= 0.25 ? 0 : curVal <= 0.6 ? 1 : 2 }
                        readonly property var _opVals: [0.1, 0.4, 0.8]

                        RowLayout {
                            anchors.fill: parent; spacing: 4

                            Text {
                                text: adminRoot._tierKo[opRow.tierIndex]
                                color: "#606080"; font.pixelSize: 10
                                font.family: adminRoot.fontFamily
                                Layout.preferredWidth: 36
                            }

                            Repeater {
                                model: ["낮음", "보통", "높음"]
                                Rectangle {
                                    Layout.fillWidth: true; height: 22; radius: 4
                                    property bool sel: opRow.selIdx() === index
                                    color: sel ? "#4A2A5A" : "#1C1C30"
                                    border.color: sel ? "#9A4ACA" : "#2A2A42"; border.width: 1
                                    Behavior on color { ColorAnimation { duration: 80 } }
                                    Text {
                                        anchors.centerIn: parent; text: modelData
                                        color: parent.sel ? "#C08AF8" : "#505078"
                                        font.pixelSize: 10; font.family: adminRoot.fontFamily
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            var tier = adminRoot._tiers[opRow.tierIndex]
                                            var val  = opRow._opVals[index]
                                            adminRoot.convParamChanged("openness", tier, val)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item { width: 1; height: 12 }
                Rectangle { width: parent.width; height: 1; color: "#222238" }
                Item { width: 1; height: 12 }

                // ── 직접성 섹션 ───────────────────────────────────────────────
                Text {
                    text: "직접성  (directness)"
                    color: "#7070A8"; font.pixelSize: 10; font.bold: true
                    font.family: adminRoot.fontFamily
                }
                Item { width: 1; height: 6 }

                RowLayout {
                    width: contentCol.width
                    spacing: 6

                    Text {
                        text: "돌려말함"
                        color: "#606080"; font.pixelSize: 10
                        font.family: adminRoot.fontFamily
                    }

                    // 커스텀 슬라이더 (preventStealing: true → ScrollView 이벤트 탈취 방지)
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
                            anchors.fill: parent
                            preventStealing: true
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
                        color: "#606080"; font.pixelSize: 10
                        font.family: adminRoot.fontFamily
                    }

                    Text {
                        text: drTrack.drVal.toFixed(2)
                        color: "#9A8060"; font.pixelSize: 10
                        font.family: adminRoot.fontFamily
                        Layout.preferredWidth: 30
                        horizontalAlignment: Text.AlignRight
                    }
                }

                Item { width: 1; height: 14 }
            }
        }
    }
}
