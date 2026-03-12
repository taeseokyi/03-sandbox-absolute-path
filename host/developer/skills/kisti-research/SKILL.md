---
name: kisti-research
description: Search Korean research databases (ScienceON, NTIS, DataON) using KISTI MCP tools
---

# KISTI Research Skill

Use this skill to search Korean scientific databases via MCP tools.

## Tool Categories

### Papers (논문) — ScienceON
| Tool | Purpose | Key Parameters |
|---|---|---|
| `kisti-mcp_search_scienceon_papers` | Search papers by keyword | `query` (Korean recommended) |
| `kisti-mcp_search_scienceon_paper_details` | Get paper details (abstract, authors, references) | `paper_id` |

### Patents (특허) — ScienceON
| Tool | Purpose | Key Parameters |
|---|---|---|
| `kisti-mcp_search_scienceon_patents` | Search patents by keyword | `query` |
| `kisti-mcp_search_scienceon_patent_details` | Get patent details (claims, applicant) | `patent_id` |
| `kisti-mcp_search_scienceon_patent_citations` | Get citation relationships | `patent_id` |

### Reports (보고서) — ScienceON
| Tool | Purpose | Key Parameters |
|---|---|---|
| `kisti-mcp_search_scienceon_reports` | Search research reports | `query` |
| `kisti-mcp_search_scienceon_report_details` | Get report details | `report_id` |

### R&D Projects (국가R&D) — NTIS
| Tool | Purpose | Key Parameters |
|---|---|---|
| `kisti-mcp_search_ntis_rnd_projects` | Search national R&D projects | `query` |
| `kisti-mcp_search_ntis_science_tech_classifications` | Browse S&T classification tree | `query` |
| `kisti-mcp_search_ntis_related_content_recommendations` | Get related content | `content_id` |

### Research Data (연구데이터) — DataON
| Tool | Purpose | Key Parameters |
|---|---|---|
| `kisti-mcp_search_dataon_research_data` | Search research datasets | `query` |
| `kisti-mcp_search_dataon_research_data_details` | Get dataset details (format, download) | `data_id` |

## User Request → Tool Mapping

| User Says | Tool to Use |
|---|---|
| "논문 검색해줘", "papers about X" | `kisti-mcp_search_scienceon_papers` |
| "특허 찾아줘", "patents for X" | `kisti-mcp_search_scienceon_patents` |
| "보고서 검색", "research reports" | `kisti-mcp_search_scienceon_reports` |
| "국가과제 검색", "NTIS 과제 검색", "R&D projects" | `kisti-mcp_search_ntis_rnd_projects` |
| "연구데이터 찾아줘", "datasets" | `kisti-mcp_search_dataon_research_data` |
| "이 논문 상세 정보" | `kisti-mcp_search_scienceon_paper_details` |
| "특허 인용 관계" | `kisti-mcp_search_scienceon_patent_citations` |

## Tips

- **Korean keywords** yield better results: "인공지능" > "AI", "자연어처리" > "NLP"
- **Workflow**: Search first → get IDs → use `_details` tools for full info
- **Combine tools**: Search papers + patents together for comprehensive research
- Results are in Korean; summarize in the user's language
