import React from 'react';
import AOIMapper from './components/AOIMapper';

function App() {
  // Example areas to analyze

  // Handle analysis completion
  const handleAnalysisComplete = (result) => {
    console.log('Analysis complete:', result);
  };

  // Handle errors
  const handleError = (error) => {
    console.error('Analysis error:', error);
  };

  return (
    <div style={{ height: "100vh", width: "100vw" }}>
      <AOIMapper
      />
    </div>
  );
}

export default App;