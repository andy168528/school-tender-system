export interface School {
  id: string; name: string; name_en: string; type: string; category: string; finance: string
  district: string; address: string; phone: string; website: string
}
export interface Site {
  site: string; monitored: boolean; reason?: string; monitor_url?: string; monitor_label?: string
  confidence?: string; last_checked?: string; last_ok?: string; fail?: number; error?: string
  browser?: boolean; tender_count?: number
}
export interface Tender {
  id: string; site: string; title: string; url: string; page: string; doc: boolean; eng_types: string[]
  first_seen: string; last_seen: string; miss: number; active: boolean; baseline?: boolean
  deadline?: string; deadline_src?: string; published?: string; published_src?: string; backup?: string
  backup_state?: 'ok' | 'dead' | 'school' | 'sys'; backup_error?: string; backup_tries?: number
  ai?: { tender: boolean; eng: boolean; summary: string; reason?: string }
}
export interface Run { at: string; mode: string; sites_checked: number; ok: number; new_tenders: number; new_eng: number; seconds: number
  backup?: { tried: number; ok: number; dead: number; school: number; sys: number; sys_msg?: string } }
export interface Meta { updated_at: string; runs: Run[] }

export type DeadlineStatus = '未截標' | '已截標' | '可能已截標' | '截標日期不明'
export interface TenderRow extends Tender {
  schools: School[]; school?: School; status: DeadlineStatus; daysLeft?: number; date: string
  types: string[]; isNew: boolean; isToday: boolean
}
export interface Data { schools: School[]; sites: Site[]; tenders: Tender[]; meta: Meta }
