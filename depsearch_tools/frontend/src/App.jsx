import { useState } from "react"

import DependencyParsingForm from "./DependencyParsingForm"
import BasicQueryComposer from "./BasicQueryComposer"
import StringQueryComposer from "./StringQueryComposer"
import AdvancedQueryComposer from "./AdvancedQueryComposer"

import './App.css'

const App = () => {
  const [advancedMode, setAdvancedMode] = useState(false)

  return (
    <div className="appContainer">
      <h1>Depsearch</h1>
      <DependencyParsingForm />
      <label className="advancedModeToggle">
        <input
          type="checkbox"
          checked={advancedMode}
          onChange={(e) => setAdvancedMode(e.target.checked)}
        />
        Advanced Mode
      </label>
      {
        advancedMode ? (
          <AdvancedQueryComposer />
        ) : (
          <StringQueryComposer />
        )
      }
    </div>
  )
}

export default App
