# tests/e2e/test_tts_e2e.py
import pytest
import json
from pathlib import Path
from requests_toolbelt.multipart import decoder


class TestTTSEndpoint:
    """TTS 엔드포인트 E2E 테스트"""
    
    @pytest.fixture
    def output_dir(self) -> Path:
        """테스트 오디오 저장 디렉토리"""
        path = Path("project/qfeed/audio_data")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_tts_returns_valid_multipart_response(self, client):
        """TTS가 유효한 Multipart 응답을 반환하는지 테스트"""
        response = client.post(
            "/ai/tts",
            json={
                "user_id": 1,
                "session_id": "100",
                "question_id": 42,
                "text": "개념에 대해 정확하게 알고 계시네요 그렇다면 조금 더 나아가서 4-way Handshake는 언제 발생하나요? 천천히 생각하시고 나서 답변해주셔도 됩니다."
            }
        )
        
        assert response.status_code == 200
        assert "multipart/mixed" in response.headers["content-type"]

    def test_tts_returns_valid_audio_and_save(self, client, output_dir):
        """TTS 오디오 유효성 검증 + 파일 저장 (수동 확인용)"""
        response = client.post(
            "/ai/tts",
            json={
                "user_id": 1,
                "session_id": "100",
                "question_id": 1,
                "text": "개념에 대해 정확하게 알고 계시네요 그렇다면 조금 더 나아가서 4-way Handshake는 언제 발생하나요? 천천히 생각하시고 나서 답변해주셔도 됩니다."
            }
        )
        
        assert response.status_code == 200
        
        # Multipart 파싱
        multipart_data = decoder.MultipartDecoder(
            response.content,
            response.headers["content-type"]
        )
        
        audio_data = None
        json_data = None
        
        for part in multipart_data.parts:
            content_type = part.headers[b'Content-Type'].decode()
            
            if 'audio/mpeg' in content_type:
                audio_data = part.content
            elif 'application/json' in content_type:
                json_data = json.loads(part.content.decode())
        
        # JSON 검증
        assert json_data is not None
        assert json_data["message"] == "get_audio_file_success"
        assert json_data["data"]["user_id"] == 1
        assert json_data["data"]["question_id"] == 1
        
        # 오디오 검증
        assert audio_data is not None
        assert audio_data[:3] == b'ID3', "MP3 ID3 태그가 없음"
        assert len(audio_data) > 1000, "오디오 파일이 너무 작음"
        
        # 파일 저장 (수동으로 들어보기 위함)
        output_path = output_dir / f"test_tts_output_{json_data['data']['question_id']}.mp3"
        with open(output_path, "wb") as f:
            f.write(audio_data)
        
        print(f"\n✅ 오디오 저장됨: {output_path}")
        print(f"   파일 크기: {len(audio_data):,} bytes")
        print(f"   재생하려면: open {output_path}")