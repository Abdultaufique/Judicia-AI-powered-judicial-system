import axios from "axios";

/**
 * Base backend URL
 * - Local dev: http://127.0.0.1:8000
 * - Production: https://c557-49-248-160-250.ngrok-free.app
 */
const API_BASE =
    import.meta.env.VITE_API_URL ||
    "http://localhost:8000";

// -------------------- ANALYZE PDF --------------------
export const analyzeDocument = async (file, onProgress) => {
    const formData = new FormData();
    formData.append("file", file, file.name);

    try {
        const response = await axios.post(`${API_BASE}/analyze`, formData, {
            headers: {
                "Content-Type": "multipart/form-data",
            },
            timeout: 180000, // 3 minutes
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percentCompleted = Math.round(
                        (progressEvent.loaded * 100) / progressEvent.total
                    );
                    onProgress(percentCompleted);
                }
            },
        });

        return { success: true, data: response.data };
    } catch (error) {
        if (error.code === "ECONNABORTED") {
            return {
                success: false,
                error: "Analysis timed out (3 min limit)",
                type: "timeout",
            };
        }

        if (error.code === "ERR_NETWORK") {
            return {
                success: false,
                error: "Could not connect to backend",
                type: "connection",
            };
        }

        return {
            success: false,
            error:
                error.response?.data?.detail ||
                error.message ||
                "Unexpected error",
            type: "error",
        };
    }
};

// -------------------- HISTORY --------------------
export const fetchHistory = async () => {
    try {
        const response = await axios.get(`${API_BASE}/history`);
        return { success: true, data: response.data };
    } catch (error) {
        return { success: false, error: error.message };
    }
};

export const fetchAnalysisById = async (id) => {
    try {
        const response = await axios.get(`${API_BASE}/history/${id}`);
        return { success: true, data: response.data };
    } catch (error) {
        return { success: false, error: error.message };
    }
};

export default {
    analyzeDocument,
    fetchHistory,
    fetchAnalysisById,
};
