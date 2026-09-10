import { create } from 'zustand';

export const useVideoStore = create((set) => ({
  // Active workflow state
  url: '',
  setUrl: (url) => set({ url }),

  metadata: null,
  setMetadata: (metadata) => set({ metadata }),

  formats: [],
  setFormats: (formats) => set({ formats }),

  aiAnalysisResult: null,
  aiAnalysisStatus: 'idle', // 'idle', 'loading', 'success', 'error', 'timeout', 'cancelled'
  aiAnalysisError: null,
  aiJobId: null,
  aiProgress: 0,
  aiStepMessage: '',
  setAiAnalysisResult: (result) => set({ aiAnalysisResult: result, aiAnalysisStatus: 'success', aiAnalysisError: null, aiProgress: 100, aiStepMessage: 'Complete' }),
  setAiAnalysisStatus: (status, error = null) => set({ aiAnalysisStatus: status, aiAnalysisError: error }),
  setAiJobProgress: (jobId, progress, stepMessage) => set({ aiJobId: jobId, aiProgress: progress, aiStepMessage: stepMessage }),

  allHashtags: [],
  setAllHashtags: (hashtags) => set({ allHashtags: hashtags }),

  isOpusMode: false,
  setIsOpusMode: (isOpusMode) => set({ isOpusMode }),

  resetWorkflow: () => set({
    url: '',
    metadata: null,
    formats: [],
    aiAnalysisResult: null,
    aiAnalysisStatus: 'idle',
    aiAnalysisError: null,
    aiJobId: null,
    aiProgress: 0,
    aiStepMessage: '',
    allHashtags: [],
    isOpusMode: false,
  })
}));
