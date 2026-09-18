from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Settings
    APP_NAME: str = "Airtable PO Generator"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # Public URL for Coolify deployment (Used for Airtable to fetch attachments)
    BASE_URL: str = Field(default="http://localhost:8000", description="Coolify 배포 공용 도메인")
    
    # Webhook Security
    WEBHOOK_SECRET: str = Field(default="", description="웹훅 인증용 비밀 토큰 (선택)")

    # Airtable Credentials
    AIRTABLE_API_KEY: str = Field(default="", description="Airtable Personal Access Token")
    AIRTABLE_BASE_ID: str = Field(default="appq6I2Rkjl8ewWs3", description="Airtable Base ID")

    # Table Names (매핑: 실제 에어테이블 'PO Created' 및 '작업내역' 테이블)
    PO_TABLE_NAME: str = Field(default="PO Created", description="부모 발주서 테이블 이름")
    ITEMS_TABLE_NAME: str = Field(default="작업내역", description="자식 작업내역/에피소드 테이블 이름")

    FIELD_CHECKBOX: str = Field(default="Create PO", description="발주서 생성 체크박스 필드명 (Create PO)")
    FIELD_ATTACHMENT: str = Field(default="PO Created", description="생성된 PDF를 저장할 첨부파일 필드")
    FIELD_STATUS: str = Field(default="", description="발주서 상태 필드 (옵션, 빈 문자열이면 업데이트 생략)")
    FIELD_ITEMS_LINK: str = Field(default="작업내역", description="자식 레코드 링크 필드명")
    FIELD_LINGUIST_NAME: str = Field(default="Linguist", description="번역가 이름 필드")
    FIELD_LINGUIST_POSITION: str = Field(default="Linguist Position", description="직무/포지션 (Linguist Position 또는 Position)")
    FIELD_LINGUIST_EMAIL: str = Field(default="Email", description="번역가 이메일")
    FIELD_DATE_ISSUED: str = Field(default="Date Issued", description="발행일")
    FIELD_DEADLINE_MONTH: str = Field(default="Deadline Month", description="마감월 (예: 2026-07)")
    FIELD_PAYMENT_STATUS: str = Field(default="Payment Status", description="결제 상태")

    # Child Table (작업내역) Field Names
    ITEM_FIELD_PROJECT: str = Field(default="Project Description", description="프로젝트/시리즈명")
    ITEM_FIELD_EPISODE: str = Field(default="Episode", description="에피소드명 (예: Ep: 19)")
    ITEM_FIELD_DEADLINE: str = Field(default="Deadline", description="마감일")
    ITEM_FIELD_ROLE: str = Field(default="Role", description="역할 (TRS, SDH 등)")
    ITEM_FIELD_RATE: str = Field(default="Final Rate", description="단가")
    ITEM_FIELD_RUNTIME: str = Field(default="Runtime", description="러닝타임")
    ITEM_FIELD_AMOUNT: str = Field(default="Amount", description="금액 (없을 시 단가*러닝타임 계산)")

    # Storage Path
    STORAGE_DIR: str = os.path.join(BASE_DIR, "storage")

settings = Settings()
