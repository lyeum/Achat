import QtQuick 2.15
import QtQuick.Controls 2.15

// 사용 설명서 오버레이 패널 (타이틀바 * 버튼으로 열림)
Item {
    id: manualRoot

    property string fontFamily: ""

    signal closeRequested

    // ── 반투명 배경 ──────────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.45
        MouseArea { anchors.fill: parent; onClicked: manualRoot.closeRequested() }
    }

    // ── 패널 본체 ────────────────────────────────────────────────────────────
    Rectangle {
        id: panel
        anchors {
            top:    parent.top;    topMargin:    48
            bottom: parent.bottom; bottomMargin: 16
            right:  parent.right;  rightMargin:  10
        }
        width: Math.min(parent.width - 20, 340)
        radius: 12
        color: "#111E2A"
        border.color: "#1E3C4A"
        border.width: 1
        clip: true

        // 헤더
        Rectangle {
            id: panelHeader
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 40
            color: "#0E1820"
            radius: 12
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 12; color: parent.color
            }
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 1; color: "#1E3C4A"
            }

            Text {
                anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
                text: "사용 설명서"
                color: "#8ABCCC"
                font.pixelSize: 15; font.bold: true
                font.family: manualRoot.fontFamily
            }

            Rectangle {
                anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                width: 24; height: 24; radius: 12
                color: closeHov.containsMouse ? "#2A3C4A" : "transparent"
                Behavior on color { ColorAnimation { duration: 100 } }
                Text { anchors.centerIn: parent; text: "✕"; color: "#607080"; font.pixelSize: 14 }
                MouseArea { id: closeHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: manualRoot.closeRequested() }
            }
        }

        // 스크롤 본문
        ScrollView {
            anchors {
                top: panelHeader.bottom; topMargin: 4
                bottom: parent.bottom;  bottomMargin: 8
                left: parent.left;      leftMargin: 2
                right: parent.right;    rightMargin: 2
            }
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical: ScrollBar {
                contentItem: Rectangle { color: "transparent" }
                background:  Rectangle { color: "transparent" }
            }

            Column {
                width: panel.width - 20
                x: 10
                spacing: 0
                topPadding: 6
                bottomPadding: 10

                // ═══════════════════════════════════════════════════
                // 대화 모드
                // ═══════════════════════════════════════════════════
                ManualSection {
                    sectionWidth: parent.width
                    fontFamily: manualRoot.fontFamily
                    badge: "대화 모드"
                    badgeColor: "#2A5060"
                    content: "지정한 캐릭터와 대화가 가능한 모드입니다.\n\n" +
                             "• Ctrl+Enter로 한글 변환이 가능합니다.\n" +
                             "• \"텍스트 입력 + *(행동/감정 표현)*\" 형태의 입력을 지원합니다. (**를 사용하지 않아도 입력 가능합니다.)\n\n" +
                             "처음엔 기본 캐릭터만 제공되며, 우측 상단 메뉴바(≡)를 통해 커스터마이징 / 캐릭터 생성 및 삭제 / 세계관 생성 및 삭제 / 세션 관리와 같은 기능들을 이용할 수 있습니다."
                }

                ManualDivider {}

                // ═══════════════════════════════════════════════════
                // 커스터마이징
                // ═══════════════════════════════════════════════════
                ManualSection {
                    sectionWidth: parent.width
                    fontFamily: manualRoot.fontFamily
                    badge: "커스터마이징"
                    badgeColor: "#2A4A30"
                    content: "대화할 캐릭터의 외형을 자유롭게 커스터마이징할 수 있습니다.\n\n" +
                             "커스터마이징으로 생성한 이미지를 캐릭터의 특정 감정 표현 시 대체할 이미지로 지정할 수도 있으니 참고하시길 바랍니다."
                }

                ManualDivider {}

                // ═══════════════════════════════════════════════════
                // 캐릭터 / 세계관 생성
                // ═══════════════════════════════════════════════════
                ManualSection {
                    sectionWidth: parent.width
                    fontFamily: manualRoot.fontFamily
                    badge: "캐릭터 / 세계관 생성"
                    badgeColor: "#3A3060"
                    content: "캐릭터의 생성 및 세계관의 생성을 지원합니다.\n\n" +
                             "캐릭터 생성의 경우 지정된 형식에 맞춰 작성하되, 잘 모르겠다면 예시 문구와 비슷한 형태로 작성하는 것이 좋습니다. 모델 특성상 중구난방인 캐릭터보다 일관성 있는 캐릭터의 대화 품질이 더 뛰어나게 나타날 수 있으니 참고해서 작성하시길 바랍니다.\n\n" +
                             "세계관 생성의 경우, 기본 Seaside 세계관 이외에 원하는 별도의 세계관을 생성할 수 있습니다. 문화 / 장소 / 스토리를 등록할 수 있으며, 각 항목별로 최소 1개 이상 작성해야 저장이 가능합니다."
                }

                ManualDivider {}

                // ═══════════════════════════════════════════════════
                // 세션 관리
                // ═══════════════════════════════════════════════════
                ManualSection {
                    sectionWidth: parent.width
                    fontFamily: manualRoot.fontFamily
                    badge: "세션 관리"
                    badgeColor: "#4A3020"
                    content: "현재 진행 중인 대화 혹은 이전에 진행했던 대화 세션으로 전환 및 삭제가 가능한 메뉴입니다.\n\n" +
                             "현재 대화 중인 캐릭터와의 세션만 표시됩니다. 다른 캐릭터와의 세션을 삭제하려면 캐릭터 변경 후 삭제해 주세요.\n\n" +
                             "응답 시간이 너무 길어진 경우:\n" +
                             "• 새 대화(기억 유지) — 현재 대화를 이어서 진행\n" +
                             "• 새 대화(기억 초기화) — 기억을 지우고 새롭게 대화"
                }

                ManualDivider {}

                // ═══════════════════════════════════════════════════
                // DB
                // ═══════════════════════════════════════════════════
                ManualSection {
                    sectionWidth: parent.width
                    fontFamily: manualRoot.fontFamily
                    badge: "DB"
                    badgeColor: "#1E3848"
                    content: "현재까지 진행한 대화 내역의 요약 / 중요 응답 / 세계관 정보 등은 DB에 저장됩니다.\n\n" +
                             "DB 항목에서 직접 창을 띄워 조회 / 수정 / 삭제 등의 동작이 가능합니다."
                }
            }
        }
    }

    // ── 인라인 컴포넌트: 섹션 블록 ──────────────────────────────────────────
    component ManualSection: Item {
        property real   sectionWidth: 300
        property string fontFamily:   ""
        property string badge:        ""
        property color  badgeColor:   "#2A4A60"
        property string content:      ""

        width:  sectionWidth
        height: badgeRow.height + bodyText.height + 12

        Row {
            id: badgeRow
            anchors { top: parent.top; topMargin: 8; left: parent.left }
            spacing: 0

            Rectangle {
                width: badgeLbl.implicitWidth + 14; height: 20; radius: 4
                color: badgeColor
                Text {
                    id: badgeLbl
                    anchors.centerIn: parent
                    text: badge
                    color: "#D0E8F0"; font.pixelSize: 12; font.bold: true
                    font.family: fontFamily
                }
            }
        }

        Text {
            id: bodyText
            anchors { top: badgeRow.bottom; topMargin: 6; left: parent.left; right: parent.right }
            text: content
            color: "#8090A0"
            font.pixelSize: 13
            font.family: fontFamily
            wrapMode: Text.Wrap
            lineHeight: 1.45
        }
    }

    // ── 인라인 컴포넌트: 구분선 ─────────────────────────────────────────────
    component ManualDivider: Rectangle {
        width:  panel.width - 24
        height: 1
        color:  "#1A2E3A"
        anchors.horizontalCenter: undefined
        x: 0
        Component.onCompleted: {
            // Column 안에서 좌우 여백만 적용
        }
    }
}
