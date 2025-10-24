import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function LoginPage() {
  const navigate = useNavigate();
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    name: ""
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const API_BASE = "http://localhost:8000";

  // Check if user is already logged in
  useEffect(() => {
    const token = localStorage.getItem("authToken");
    if (token) {
      console.log("User already logged in, redirecting to upload...");
      navigate("/upload");
    }
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = isLogin ? "/login" : "/signup";
      console.log("Calling endpoint:", `${API_BASE}${endpoint}`);
      
      const response = await axios.post(`${API_BASE}${endpoint}`, formData, {
        timeout: 10000,
      });
      
      console.log("API Response:", response.data);
      
      if (response.data.access_token) {
        // Store authentication data
        localStorage.setItem("userId", response.data.user_id.toString());
        localStorage.setItem("authToken", response.data.access_token);
        
        console.log("Stored userId:", response.data.user_id);
        console.log("Stored token:", response.data.access_token);
        
        // Force navigation with a slight delay
        setTimeout(() => {
          console.log("Navigating to /upload");
          navigate("/upload", { replace: true });
        }, 100);
      } else {
        setError("Authentication failed - no token received");
      }
    } catch (error: any) {
      console.error("Login error:", error);
      
      if (error.response) {
        setError(error.response.data.detail || `Server error: ${error.response.status}`);
      } else if (error.request) {
        setError("Cannot connect to server. Please make sure the backend is running.");
      } else {
        setError(error.message || "An unexpected error occurred");
      }
    } finally {
      setLoading(false);
    }
  };

  // ... rest of the component remains the same

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center">
      <div className="bg-overlay"></div>

      <div className="auth-card relative z-10 w-full max-w-md">
        <h2 className="auth-title">{isLogin ? "Login" : "Sign Up"}</h2>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            <strong>Error:</strong> {error}
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit}>
          {!isLogin && (
            <input 
              type="text" 
              name="name"
              placeholder="Full Name" 
              className="auth-input" 
              required 
              value={formData.name}
              onChange={handleInputChange}
              disabled={loading}
            />
          )}
          <input 
            type="email" 
            name="email"
            placeholder="Email" 
            className="auth-input" 
            required 
            value={formData.email}
            onChange={handleInputChange}
            disabled={loading}
          />
          <input 
            type="password" 
            name="password"
            placeholder="Password" 
            className="auth-input" 
            required 
            value={formData.password}
            onChange={handleInputChange}
            disabled={loading}
          />
          <button 
            type="submit" 
            className="auth-btn disabled:opacity-50"
            disabled={loading}
          >
            {loading ? "Processing..." : (isLogin ? "Login" : "Sign Up")}
          </button>
        </form>

        <p className="text-center mt-4 text-sm text-gray-600">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button 
            className="auth-link" 
            onClick={() => setIsLogin(!isLogin)}
            disabled={loading}
          >
            {isLogin ? "Sign Up" : "Login"}
          </button>
        </p>
      </div>
    </div>
  );
}