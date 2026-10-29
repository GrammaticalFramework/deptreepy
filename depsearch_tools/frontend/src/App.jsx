import { useState } from "react"

import DependencyParsingForm from "./DependencyParsingForm"
import BasicQueryComposer from "./BasicQueryComposer"
import StringQueryComposer from "./StringQueryComposer"
import AdvancedQueryComposer from "./AdvancedQueryComposer"

import './App.css'

const INSTRUCTION_URL = 'https://github.com/GrammaticalFramework/deptreepy/tree/depsearch/docs/ui-manual'

const App = () => {
  const [advancedMode, setAdvancedMode] = useState(false)

  return (
    <div className="appContainer">
      <h1>Depsearch</h1>
      <DependencyParsingForm />
      <div className="modeRow">
        <label className="advancedModeToggle">
          <input
            type="checkbox"
            checked={advancedMode}
            onChange={(e) => setAdvancedMode(e.target.checked)}
          />
          Advanced Mode
        </label>
        <a
          className="instructionButton"
          href={INSTRUCTION_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          Instruction <i className="bi bi-question-circle"></i>
        </a>
      </div>
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
