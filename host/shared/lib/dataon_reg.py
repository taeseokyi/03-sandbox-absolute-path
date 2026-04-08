from typing import Optional, Union
from enum import Enum
from pydantic import BaseModel, Field


# ──────────────────────────────────────────
# ENUM 정의
# ──────────────────────────────────────────

class 관계유형_과제(str, Enum):
    유발과제 = "isOutputOf"
    관련과제 = "hasOutput"
    해당사항없음 = "none"

class 식별자유형_과제(str, Enum):
    NTIS = "NTIS"
    DOI  = "DOI"
    ETC  = "ETC"

class 관계유형_논문(str, Enum):
    유발논문 = "isOutputOf"
    관련논문 = "hasOutput"
    해당사항없음 = "none"

class 국내외구분(str, Enum):
    국내 = "DOMESTIC"
    국외 = "ABROAD"

class 인물구분(str, Enum):
    생성자 = "CREATOR"
    담당자 = "MANAGER"
    기여자 = "CONTRIBUTOR"

class 이메일도메인(str, Enum):
    직접입력  = "직접입력"
    naver    = "naver.com"
    hanmail  = "hanmail.net"
    nate     = "nate.com"
    gmail    = "gmail.com"

class 수집지역유형(str, Enum):
    Point   = "geoLocationPoint"
    Place   = "geoLocationPlace"
    Line    = "geoLocationLine"
    Box     = "geoLocationBox"
    Polygon = "geoLocationPolygon"

class 공개구분_데이터(str, Enum):
    즉시공개 = "PUBLIC"
    엠바고   = "EMBARGO"

class 공개구분_파일(str, Enum):
    파일공개   = "PUBLIC"
    엠바고     = "PROTECTED"
    파일비공개 = "PRIVATE"

class 라이선스(str, Enum):
    저작자표시                    = "저작자표시"
    저작자표시_비영리             = "저작자표시-비영리"
    저작자표시_변경금지           = "저작자표시-변경금지"
    저작자표시_동일조건변경허락   = "저작자표시-동일조건변경허락"
    저작자표시_비영리_동일조건    = "저작자표시-비영리-동일조건변경허락"
    저작자표시_비영리_변경금지    = "저작자표시-비영리-변경금지"
    기타                         = "기타"


# ──────────────────────────────────────────
# 공통 모델
# ──────────────────────────────────────────

class 이메일(BaseModel):
    id:     Optional[str]         = None
    domain: Optional[이메일도메인] = 이메일도메인.직접입력


class 좌표(BaseModel):
    위도: Optional[float] = None
    경도: Optional[float] = None


# ──────────────────────────────────────────
# 수집지역 정보 (유형별)
# ──────────────────────────────────────────

class 수집지역_Point(BaseModel):
    """단일 좌표 1쌍 고정"""
    위도: Optional[float] = None
    경도: Optional[float] = None

class 수집지역_Place(BaseModel):
    """지역명 문자열 1개"""
    지역명: Optional[str] = None

class 수집지역_Line(BaseModel):
    """2쌍 이상, + 버튼으로 가변 추가"""
    좌표목록: list[좌표] = Field(default_factory=list, min_length=2)

class 수집지역_Box(BaseModel):
    """4쌍 고정, 추가 불가"""
    좌표목록: list[좌표] = Field(default_factory=lambda: [좌표() for _ in range(4)], min_length=4, max_length=4)

class 수집지역_Polygon(BaseModel):
    """최소 4쌍 기본 제공, + 버튼으로 가변 추가"""
    좌표목록: list[좌표] = Field(default_factory=lambda: [좌표() for _ in range(4)], min_length=4)


# ──────────────────────────────────────────
# 연관정보 - 과제정보
# ──────────────────────────────────────────

class 과제책임자(BaseModel):
    책임자명_한글:    Optional[str] = None
    책임자명_영문:    Optional[str] = None
    기관명_한글:      Optional[str] = None
    국가연구자번호:   Optional[str] = Field(None, pattern=r'^\d{8}$', description="'-' 제외한 8자리 숫자")

class 과제참여자(BaseModel):
    참여자명_한글:   Optional[str] = None
    참여자명_영문:   Optional[str] = None
    기관명_한글:     Optional[str] = None
    국가연구자번호:  Optional[str] = Field(None, pattern=r'^\d{8}$', description="'-' 제외한 8자리 숫자")

class 과제상세정보(BaseModel):
    """상세입력 토글 ON 시 활성화"""
    참여자목록:      list[과제참여자] = Field(default_factory=list)   # ← LIST
    출처서비스:      Optional[str]   = None
    과제수행국가코드: Optional[str]  = None
    과제URL:        Optional[str]   = None
    연구내용:       Optional[str]   = None
    키워드_한글:    list[str]        = Field(default_factory=list)
    키워드_영문:    list[str]        = Field(default_factory=list)
    과제관리기관:   Optional[str]    = None
    기준년도:       Optional[str]   = None
    연구기간_시작일: Optional[str]  = Field(None, description="yyyy-mm-dd")
    연구기간_종료일: Optional[str]  = Field(None, description="yyyy-mm-dd")
    총연구비:       Optional[float] = None

_과제책임자_T = 과제책임자   # 필드명과 클래스명 충돌 방지용 별칭

class 과제정보(BaseModel):
    관계유형:        관계유형_과제              = Field(..., description="필수")
    식별자유형:      Optional[식별자유형_과제]  = None
    식별자:         Optional[str]             = None
    과제명_한글:    Optional[str]             = None
    과제명_영문:    Optional[str]             = None
    부처명:         Optional[str]             = None
    과학기술표준분류: Optional[str]           = None
    과제수행기관:   Optional[str]             = None
    과제책임자:     Optional[_과제책임자_T]   = None   # _T alias: 필드명 == 클래스명 Python 버그 우회
    상세입력:       Optional[과제상세정보]     = None   # 토글 ON 시


# ──────────────────────────────────────────
# 연관정보 - 논문정보
# ──────────────────────────────────────────

class 저널정보(BaseModel):
    ISSN: Optional[str] = None
    ISBN: Optional[str] = None
    권:   Optional[str] = None
    호:   Optional[str] = None

class 논문상세정보(BaseModel):
    """상세입력 토글 ON 시 활성화"""
    국가코드:   Optional[str]   = None
    출처서비스: Optional[str]   = None
    초록:      Optional[str]    = None
    키워드_한글: list[str]      = Field(default_factory=list)
    키워드_영문: list[str]      = Field(default_factory=list)
    출판사:    Optional[str]    = None
    저널명:    Optional[str]    = None
    저널정보:  Optional[저널정보] = None
    원문URL:   Optional[str]   = None

class 논문정보(BaseModel):
    관계유형:   관계유형_논문              = Field(..., description="필수")
    식별자유형: Optional[str]            = None
    식별자:    Optional[str]            = None
    DOI:       Optional[str]           = None
    제목_한글: Optional[str]            = None
    제목_영문: Optional[str]            = None
    저자:      Optional[str]           = None
    발행년도:  Optional[str]           = None
    상세입력:  Optional[논문상세정보]    = None   # 토글 ON 시


# ──────────────────────────────────────────
# 기본정보
# ──────────────────────────────────────────

class 언어선택(BaseModel):
    주언어: str = Field(default="KO", description="필수")
    부언어: str = Field(default="EN")

class 기본정보(BaseModel):
    국내외:          국내외구분     = Field(..., description="필수")
    언어:            언어선택       = Field(default_factory=언어선택)
    제목_주언어:     str            = Field(..., description="필수")
    제목_부언어:     Optional[str]  = None
    설명_주언어:     str            = Field(..., description="필수, 마크다운 지원")
    설명_부언어:     Optional[str]  = Field(None, description="마크다운 지원")
    키워드_주언어:   list[str]      = Field(..., description="필수")        # ← LIST
    키워드_부언어:   list[str]      = Field(default_factory=list)
    과학기술표준분류: list[str]     = Field(..., description="필수, AI 추천 제공")  # ← LIST
    생성일자:        Optional[str] = Field(None, description="yyyy-mm-dd")


# ──────────────────────────────────────────
# 인물정보
# ──────────────────────────────────────────

class 인물(BaseModel):
    역할:           인물구분               = Field(..., description="필수")
    이름_주언어:   Optional[str]          = None
    이름_부언어:   Optional[str]          = None
    기관_주언어:   Optional[str]          = None
    기관_부언어:   Optional[str]          = None
    email:         Optional[이메일]       = None
    국가연구자번호: Optional[str]         = Field(None, pattern=r'^\d{8}$', description="'-' 제외한 8자리 숫자")
    ORCID:         Optional[str]         = None


# ──────────────────────────────────────────
# 추가정보
# ──────────────────────────────────────────

class 수집기간(BaseModel):
    시작일자: Optional[str] = Field(None, description="yyyy-mm-dd")
    종료일자: Optional[str] = Field(None, description="yyyy-mm-dd")

class 수집지역(BaseModel):
    유형: 수집지역유형 = Field(default=수집지역유형.Polygon)
    수집지역정보: Optional[
        Union[
            수집지역_Point,
            수집지역_Place,
            수집지역_Line,
            수집지역_Box,
            수집지역_Polygon
        ]
    ] = None

class 추가정보(BaseModel):
    데이터수집기간: list[수집기간]  = Field(default_factory=list)  # ← LIST
    데이터수집지역: list[수집지역]  = Field(default_factory=list)  # ← LIST


# ──────────────────────────────────────────
# 공개 및 라이선스 설정
# ──────────────────────────────────────────

class 엠바고설정_데이터(BaseModel):
    공개일자: Optional[str] = Field(None, description="yyyy-mm-dd, 최대 2년 이후")

class 공개및라이선스설정(BaseModel):
    공개구분:   공개구분_데이터              = Field(default=공개구분_데이터.즉시공개)
    엠바고설정: Optional[엠바고설정_데이터] = Field(None, description="EMBARGO 선택 시 활성화")
    DOI출판:   bool                        = Field(default=True, description="필수. 승인 완료 시 DOI 자동 발급")
    라이선스종류:  Optional[라이선스]           = None


# ──────────────────────────────────────────
# 파일 데이터
# ──────────────────────────────────────────

class 엠바고설정_파일(BaseModel):
    공개일자: Optional[str] = Field(None, description="yyyy-mm-dd. 해당 일자에 파일공개로 전환")

class 데이터파일(BaseModel):
    파일명:    Optional[str]              = None
    파일설명:  Optional[str]             = Field(None, description="파일에 대한 간략한 설명을 입력하세요.")
    공개구분:  공개구분_파일              = Field(default=공개구분_파일.파일공개, description="필수")
    엠바고설정: Optional[엠바고설정_파일] = Field(None, description="PROTECTED 선택 시 활성화")

class 파일데이터(BaseModel):
    note: str = "데이터 파일 또는 출처URL 중 하나 필수"
    파일목록: list[데이터파일] = Field(default_factory=list)
    출처URL:  list[str]        = Field(default_factory=list, description="+ 버튼으로 여러 URL 추가 가능")  # ← LIST


# ──────────────────────────────────────────
# 최상위 - 연구데이터 등록 폼
# ──────────────────────────────────────────

class 연관정보(BaseModel):
    note:     str              = "필수 아님. 입력 시 자동완성 추천 목록 제공"
    과제목록: list[과제정보]  = Field(default_factory=list)  # ← LIST
    논문목록: list[논문정보]  = Field(default_factory=list)  # ← LIST

class DataON_연구데이터등록(BaseModel):
    collection: str = "국가연구데이터플랫폼"
    연관:         연관정보              = Field(default_factory=연관정보)
    기본:         기본정보
    인물정보:     list[인물]            = Field(..., description="필수. 생성자 최소 1명")  # ← LIST
    추가:         추가정보              = Field(default_factory=추가정보)
    공개설정:     공개및라이선스설정    = Field(default_factory=공개및라이선스설정)
    파일:         파일데이터            = Field(default_factory=파일데이터)


# ──────────────────────────────────────────
# 사용 예시
# ──────────────────────────────────────────

if __name__ == "__main__":

    form = DataON_연구데이터등록(
        기본=기본정보(
            국내외=국내외구분.국내,
            제목_주언어="기후변화 관련 해양 수온 관측 데이터",
            제목_부언어="Ocean Temperature Observation Data for Climate Change",
            설명_주언어="2020~2024년 동해 수온 변화를 측정한 데이터셋입니다.",
            설명_부언어="Dataset measuring East Sea temperature changes from 2020 to 2024.",
            키워드_주언어=["수온", "동해", "기후변화"],
            키워드_부언어=["sea temperature", "East Sea", "climate change"],
            과학기술표준분류=["해양학", "기후학"],
            생성일자="2024-01-15",
        ),
        인물정보=[
            인물(
                역할=인물구분.생성자,
                이름_주언어="홍길동",
                이름_부언어="Gildong Hong",
                기관_주언어="한국해양연구원",
                email=이메일(id="hong", domain=이메일도메인.gmail),
                국가연구자번호="12345678",
            )
        ],
        추가=추가정보(
            데이터수집기간=[
                수집기간(시작일자="2020-01-01", 종료일자="2024-12-31")
            ],
            데이터수집지역=[
                수집지역(
                    유형=수집지역유형.Polygon,
                    수집지역정보=수집지역_Polygon(
                        좌표목록=[
                            좌표(위도=37.5, 경도=129.0),
                            좌표(위도=38.0, 경도=130.0),
                            좌표(위도=37.0, 경도=130.5),
                            좌표(위도=37.5, 경도=129.0),
                        ]
                    )
                )
            ],
        ),
        공개설정=공개및라이선스설정(
            공개구분=공개구분_데이터.즉시공개,
            DOI출판=True,
            라이선스종류=라이선스.저작자표시,
        ),
        파일=파일데이터(
            파일목록=[
                데이터파일(
                    파일명="ocean_temp_2020_2024.csv",
                    파일설명="동해 수온 측정 원시 데이터",
                    공개구분=공개구분_파일.파일공개,
                )
            ],
            출처URL=["https://example.com/data/ocean_temp"],
        ),
    )

    import json
    print(json.dumps(form.model_dump(), ensure_ascii=False, indent=2))
