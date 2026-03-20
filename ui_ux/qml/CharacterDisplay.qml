import QtQuick 2.15

// 캐릭터 표시 컴포넌트
//
// 레이어 순서 (아래 → 위):
//   [A] icons/{characterId}/{characterId}.png  ← 기본 아이콘 (있는 경우)
//   OR
//   [B] characters/{type}/*.png 파츠 합성 (base→cloth→hair→eye→mouth)
//
//   [+] icons/{characterId}/emotion/{currentMood}.png  ← 감정 오버레이 (있는 경우)
//
// 에셋이 없으면 mood별 이모지 플레이스홀더를 표시한다.
Item {
    id: charRoot
    width:  128
    height: 160

    property string characterId: ""     // 캐릭터 ID (Haru 등) — 아이콘/감정 경로 기준
    property string partsJson:   "{}"   // parts.json 내용 (파츠 합성 시 사용)
    property string currentMood: "neutral"

    // ── 파싱된 파츠 설정 ──────────────────────────────────────────────────────
    readonly property var _p: { try { return JSON.parse(partsJson) } catch(e) { return {} } }

    // icons/{id}/{id}.png 경로
    readonly property url _iconUrl: characterId !== ""
        ? Qt.resolvedUrl("../assets/icons/" + characterId + "/" + characterId + ".png")
        : ""

    // 기본 아이콘이 로드됐는지 (파츠 레이어 합성 대신 사용)
    readonly property bool _useIcon: characterId !== "" && iconImg.status === Image.Ready

    // 파츠가 하나라도 선택됐는지
    readonly property bool _hasAnyPart: _useIcon
        || !!_p.base || !!_p.hair || !!_p.eye || !!_p.mouth || !!_p.cloth

    // ── 에셋 경로 헬퍼 ────────────────────────────────────────────────────────
    function _partsUrl(type, file) {
        if (!file) return ""
        return Qt.resolvedUrl("../assets/characters/" + type + "/" + file)
    }
    function _emotionUrl(mood) {
        if (!characterId) return ""
        return Qt.resolvedUrl(
            "../assets/icons/" + characterId + "/emotion/" + mood + ".png"
        )
    }

    // ── [A] 기본 아이콘 (icons/{id}/{id}.png) ─────────────────────────────────
    Image {
        id: iconImg
        anchors.fill: parent
        source: charRoot._iconUrl
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }

    // ── [B] 파츠 합성 (아이콘이 없을 때) ─────────────────────────────────────

    // 레이어 1: base (얼굴/몸통 베이스)
    Image {
        anchors.fill: parent
        source: !charRoot._useIcon ? charRoot._partsUrl("base", charRoot._p.base) : ""
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }

    // 레이어 2: cloth (의상)
    Image {
        anchors.fill: parent
        source: !charRoot._useIcon ? charRoot._partsUrl("cloth", charRoot._p.cloth) : ""
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }

    // 레이어 3: hair (헤어)
    Image {
        anchors.fill: parent
        source: !charRoot._useIcon ? charRoot._partsUrl("hair", charRoot._p.hair) : ""
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }

    // 레이어 4: eye (눈)
    Image {
        anchors.fill: parent
        source: !charRoot._useIcon ? charRoot._partsUrl("eye", charRoot._p.eye) : ""
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }

    // 레이어 5: mouth (입)
    Image {
        anchors.fill: parent
        source: !charRoot._useIcon ? charRoot._partsUrl("mouth", charRoot._p.mouth) : ""
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }

    // ── 감정 오버레이 (icons/{id}/emotion/{mood}.png) ─────────────────────────
    Image {
        id: emotionLayer
        anchors.fill: parent
        source: charRoot._emotionUrl(charRoot.currentMood)
        fillMode: Image.PreserveAspectFit
        visible: status === Image.Ready
    }

    // ── 플레이스홀더 (에셋 없을 때) ───────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#2A2A2A"
        radius: 8
        visible: !charRoot._hasAnyPart

        Text {
            anchors.centerIn: parent
            text: {
                if (charRoot.currentMood === "happy")        return "😊"
                if (charRoot.currentMood === "affectionate") return "🥰"
                if (charRoot.currentMood === "touched")      return "🥹"
                if (charRoot.currentMood === "curious")      return "🤔"
                if (charRoot.currentMood === "sad")          return "😢"
                if (charRoot.currentMood === "embarrassed")  return "😳"
                if (charRoot.currentMood === "annoyed")      return "😤"
                if (charRoot.currentMood === "angry")        return "😠"
                return "😐"
            }
            font.pixelSize: 40
        }
    }
}
