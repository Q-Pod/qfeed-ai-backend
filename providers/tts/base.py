from typing import Protocol


class TTSProvider(Protocol):
    """TTS Provider 인터페이스"""
    
    async def synthesize(self, text: str) -> bytes:
        """
        텍스트를 음성으로 변환
        
        Args:
            text: 변환할 텍스트
            
        Returns:
            오디오 바이너리 데이터
        """
        ...