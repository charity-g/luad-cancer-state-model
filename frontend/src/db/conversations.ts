/**
 * IndexedDB persistence for per-profile conversation sessions.
 *
 * Schema
 * ------
 * Database:  luad_cell_model  (v1)
 * Store:     conversations
 *   key:     session_id  (string uuid, provided by caller)
 *   indexes: profile_id
 *
 * Each record stores the full ordered message array for one conversation.
 */

import type { ChatMessage } from '../hooks/useChat'

const DB_NAME    = 'luad_cell_model'
const DB_VERSION = 1
const STORE      = 'conversations'

export interface ConversationRecord {
  session_id:  string
  profile_id:  string
  created_at:  number   // ms since epoch
  updated_at:  number
  title:       string   // first user message, truncated
  messages:    ChatMessage[]
}

// ── open / upgrade ───────────────────────────────────────────────────────────

let _db: IDBDatabase | null = null

function openDB(): Promise<IDBDatabase> {
  if (_db) return Promise.resolve(_db)

  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)

    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'session_id' })
        store.createIndex('profile_id', 'profile_id', { unique: false })
        store.createIndex('updated_at', 'updated_at', { unique: false })
      }
    }

    req.onsuccess  = (e) => { _db = (e.target as IDBOpenDBRequest).result; resolve(_db) }
    req.onerror    = () => reject(req.error)
    req.onblocked  = () => reject(new Error('IndexedDB blocked'))
  })
}

// ── public API ────────────────────────────────────────────────────────────────

export async function saveConversation(record: ConversationRecord): Promise<void> {
  const db    = await openDB()
  const title = record.messages.find((m) => m.role === 'user')?.content.slice(0, 60) ?? 'New conversation'
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).put({ ...record, title, updated_at: Date.now() })
    req.onsuccess = () => resolve()
    req.onerror   = () => reject(req.error)
  })
}

export async function loadConversation(session_id: string): Promise<ConversationRecord | null> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readonly').objectStore(STORE).get(session_id)
    req.onsuccess = () => resolve((req.result as ConversationRecord) ?? null)
    req.onerror   = () => reject(req.error)
  })
}

export async function listConversations(profile_id: string): Promise<ConversationRecord[]> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const index = db.transaction(STORE, 'readonly').objectStore(STORE).index('profile_id')
    const req   = index.getAll(IDBKeyRange.only(profile_id))
    req.onsuccess = () => {
      const rows = (req.result as ConversationRecord[]) ?? []
      resolve(rows.sort((a, b) => b.updated_at - a.updated_at))
    }
    req.onerror = () => reject(req.error)
  })
}

export async function deleteConversation(session_id: string): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readwrite').objectStore(STORE).delete(session_id)
    req.onsuccess = () => resolve()
    req.onerror   = () => reject(req.error)
  })
}
