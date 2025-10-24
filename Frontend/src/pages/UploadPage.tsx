import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const UploadPage: React.FC = () => {
  const [extractedText, setExtractedText] = useState("");
  const [simplifiedText, setSimplifiedText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [annotatedSimplified, setAnnotatedSimplified] = useState("");
  const [simplifyLevel, setSimplifyLevel] = useState("simple");
  const [language, setLanguage] = useState("");
  const [compareView, setCompareView] = useState(false);
  const [loading, setLoading] = useState({
    extract: false,
    simplify: false,
    translate: false
  });
  
  const navigate = useNavigate();
  const API_BASE = "http://localhost:8000";

  // Get auth token from localStorage
  const getAuthHeader = () => {
    const token = localStorage.getItem("authToken");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const handleLogout = () => {
    localStorage.removeItem("authToken");
    localStorage.removeItem("userId");
    navigate("/");
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(prev => ({...prev, extract: true}));
    
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API_BASE}/extract-text`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
          ...getAuthHeader()
        },
      });
      
      setExtractedText(response.data.extracted_text);
      // Reset simplified and translated text when new file is uploaded
      setSimplifiedText("");
      setTranslatedText("");
      setAnnotatedSimplified("");
    } catch (error: any) {
      console.error("Error extracting text:", error);
      if (error.response?.status === 401) {
        handleLogout();
      } else {
        alert("Error extracting text from document");
      }
    } finally {
      setLoading(prev => ({...prev, extract: false}));
    }
  };

  const handleSimplify = async () => {
    if (!extractedText) return;
    
    setLoading(prev => ({...prev, simplify: true}));
    
    try {
      const response = await axios.post(`${API_BASE}/simplify`, {
        text: extractedText,
        level: simplifyLevel
      }, {
        headers: getAuthHeader()
      });
      
      setSimplifiedText(response.data.simplified_text);
      setAnnotatedSimplified(response.data.annotated_simplified || response.data.simplified_text);
      // Reset translated text when new simplification is done
      setTranslatedText("");
    } catch (error: any) {
      console.error("Error simplifying text:", error);
      if (error.response?.status === 401) {
        handleLogout();
      } else {
        alert("Error simplifying text");
      }
    } finally {
      setLoading(prev => ({...prev, simplify: false}));
    }
  };

  const handleTranslate = async () => {
    if (!simplifiedText || !language) return;
    
    setLoading(prev => ({...prev, translate: true}));
    
    try {
      const response = await axios.post(`${API_BASE}/translate`, {
        text: simplifiedText,
        language: language
      }, {
        headers: getAuthHeader()
      });
      
      setTranslatedText(response.data.translated_text);
    } catch (error: any) {
      console.error("Error translating text:", error);
      if (error.response?.status === 401) {
        handleLogout();
      } else {
        alert("Error translating text");
      }
    } finally {
      setLoading(prev => ({...prev, translate: false}));
    }
  };

  const handleDownload = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { 
      type: type === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document" 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const indianLanguages = [
    "Hindi", "Bengali", "Telugu", "Marathi", "Tamil", "Urdu", "Gujarati",
    "Kannada", "Odia", "Punjabi", "Malayalam", "Assamese", "Maithili",
    "Santali", "Konkani", "Manipuri", "Bodo", "Dogri", "Kashmiri", "Sindhi", "Sanskrit"
  ];

  return (
    <div className="min-h-screen w-full bg-gray-100 p-6 flex flex-col">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">
          Legal Document Simplifier
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-gray-600">
            User ID: {localStorage.getItem("userId")}
          </span>
          <button
            onClick={handleLogout}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg shadow"
          >
            Logout
          </button>
          <button
            onClick={() => setCompareView(!compareView)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg shadow"
          >
            {compareView ? "Hide Compare View" : "Compare View"}
          </button>
        </div>
      </div>

      {/* Upload Section */}
      <div className="flex-1 flex flex-col gap-6">
        <div className="border-2 border-dashed border-gray-400 rounded-xl p-6 bg-white shadow text-center">
          <input
            type="file"
            accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"
            onChange={handleFileUpload}
            className="mb-4"
            disabled={loading.extract}
          />
          <p className="text-gray-500">
            {loading.extract ? "Extracting text..." : "Upload a document to simplify"}
          </p>
        </div>

        {/* Extracted Text */}
        {extractedText && (
          <div className="bg-white p-4 rounded-xl shadow">
            <h2 className="text-xl font-semibold mb-2">Extracted Text</h2>
            <textarea
              value={extractedText}
              readOnly
              className="w-full h-32 border rounded-lg p-2"
            />
          </div>
        )}

        {/* Simplification Options */}
        {extractedText && (
          <div className="bg-white p-4 rounded-xl shadow">
            <h2 className="text-xl font-semibold mb-2">Simplification Level</h2>
            <div className="flex gap-4 mb-4">
              {["simple", "moderate", "advanced"].map((level) => (
                <label key={level} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="simplify"
                    value={level}
                    checked={simplifyLevel === level}
                    onChange={(e) => setSimplifyLevel(e.target.value)}
                  />
                  {level.charAt(0).toUpperCase() + level.slice(1)}
                </label>
              ))}
            </div>
            <button
              onClick={handleSimplify}
              disabled={loading.simplify}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg shadow disabled:opacity-50"
            >
              {loading.simplify ? "Simplifying..." : "Simplify"}
            </button>
          </div>
        )}

        {/* Simplified Text with Color Coding */}
        {simplifiedText && (
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Simplified Text</h2>
              <span className="text-sm text-gray-500">
                {simplifiedText.split(/\s+/).length} words
              </span>
            </div>
            
            {/* Color-coded annotated text */}
            <div className="bg-green-50 p-4 rounded-lg border border-green-200 mb-4">
              <div 
                className="w-full p-4 border rounded-lg bg-white min-h-40 overflow-y-auto"
                dangerouslySetInnerHTML={{ __html: annotatedSimplified }}
              />
            </div>
            
            {/* Plain text version */}
            <div className="mb-4">
              <h3 className="font-medium mb-2">Plain Text Version:</h3>
              <textarea
                value={simplifiedText}
                readOnly
                className="w-full h-32 border rounded-lg p-2"
              />
            </div>
            
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => handleDownload(simplifiedText, "simplified.txt", "text/plain")}
                className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-2 rounded-lg"
              >
                Download TXT
              </button>
              <button
                onClick={() => handleDownload(simplifiedText, "simplified.docx", "docx")}
                className="bg-purple-500 hover:bg-purple-600 text-white px-3 py-2 rounded-lg"
              >
                Download DOCX
              </button>
            </div>
          </div>
        )}

        {/* Color Legend */}
        {simplifiedText && (
          <div className="bg-white p-4 rounded-xl shadow">
            <h3 className="text-lg font-semibold mb-3">Risk Legend</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries({
                "obligation": "#3B82F6",
                "penalty": "#EF4444", 
                "condition": "#F97316",
                "right": "#10B981",
                "definition": "#8B5CF6",
                "limitation": "#6366F1",
                "termination": "#EC4899"
              }).map(([category, color]) => (
                <div key={category} className="flex items-center">
                  <div 
                    className="w-4 h-4 rounded mr-2" 
                    style={{ backgroundColor: `${color}20`, border: `1px solid ${color}` }}
                  ></div>
                  <span className="text-sm capitalize">{category}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Translation Section */}
        {simplifiedText && (
          <div className="bg-white p-4 rounded-xl shadow">
            <h2 className="text-xl font-semibold mb-2">Translate</h2>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="border p-2 rounded-lg w-full mb-3"
            >
              <option value="">Select Language</option>
              {indianLanguages.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </select>
            <button
              onClick={handleTranslate}
              disabled={!language || loading.translate}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg shadow disabled:opacity-50"
            >
              {loading.translate ? "Translating..." : "Translate"}
            </button>
          </div>
        )}

        {/* Translated Text */}
        {translatedText && (
          <div className="bg-white p-4 rounded-xl shadow">
            <h2 className="text-xl font-semibold mb-2">Translated Text</h2>
            <textarea
              value={translatedText}
              readOnly
              className="w-full h-32 border rounded-lg p-2"
            />
            <div className="flex gap-3 mt-3">
              <button
                onClick={() => handleDownload(translatedText, "translated.txt", "text/plain")}
                className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded-lg"
              >
                Download TXT
              </button>
              <button
                onClick={() => handleDownload(translatedText, "translated.docx", "docx")}
                className="bg-purple-500 hover:bg-purple-600 text-white px-3 py-1 rounded-lg"
              >
                Download DOCX
              </button>
            </div>
          </div>
        )}

        {/* Compare View */}
        {compareView && (
          <div className="bg-gray-50 p-6 rounded-xl shadow grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <h3 className="font-bold mb-2">Extracted</h3>
              <div className="p-2 border rounded bg-white h-64 overflow-y-auto">
                {extractedText || "No text extracted"}
              </div>
            </div>
            <div>
              <h3 className="font-bold mb-2">Simplified</h3>
              <div className="p-2 border rounded bg-white h-64 overflow-y-auto">
                {simplifiedText || "No simplified text"}
              </div>
            </div>
            <div>
              <h3 className="font-bold mb-2">Translated</h3>
              <div className="p-2 border rounded bg-white h-64 overflow-y-auto">
                {translatedText || "No translated text"}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadPage;