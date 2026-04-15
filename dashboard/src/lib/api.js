import axios from 'axios'

const client = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
})

export const api = {
  getAccounts: () =>
    client.get('/api/accounts').then(r => r.data),

  getAccountOverview: (accountId, datePreset = 'last_7d') =>
    client.get(`/api/accounts/${accountId}/overview`, { params: { date_preset: datePreset } }).then(r => r.data),

  getAccountTimeseries: (accountId, datePreset = 'last_30d') =>
    client.get(`/api/accounts/${accountId}/timeseries`, { params: { date_preset: datePreset } }).then(r => r.data),

  getCampaigns: (accountId, datePreset = 'last_7d') =>
    client.get(`/api/accounts/${accountId}/campaigns`, { params: { date_preset: datePreset } }).then(r => r.data),

  getCampaignTimeseries: (campaignId, datePreset = 'last_30d') =>
    client.get(`/api/campaigns/${campaignId}/timeseries`, { params: { date_preset: datePreset } }).then(r => r.data),

  getAdSets: (campaignId, datePreset = 'last_7d') =>
    client.get(`/api/campaigns/${campaignId}/adsets`, { params: { date_preset: datePreset } }).then(r => r.data),

  getAd: (adId) =>
    client.get(`/api/ads/${adId}`).then(r => r.data),

  getAdTimeseries: (adId, datePreset = 'last_30d') =>
    client.get(`/api/ads/${adId}/timeseries`, { params: { date_preset: datePreset } }).then(r => r.data),

  getAdset: (adsetId) =>
    client.get(`/api/adsets/${adsetId}`).then(r => r.data),

  getAds: (adsetId, datePreset = 'last_7d') =>
    client.get(`/api/adsets/${adsetId}/ads`, { params: { date_preset: datePreset } }).then(r => r.data),

  updateStatus: (type, id, status) =>
    client.post(`/api/${type}s/${id}/status`, { status }).then(r => r.data),
}

export default api
