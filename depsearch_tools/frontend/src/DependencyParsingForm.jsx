import { useState } from 'react'
import "./DependencyParsingForm.css"

import { parseDependencies } from './services/dependencyParsing'

const DependencyParsingForm = () => {
  const [text, setText] = useState('')
  const [language, setLanguage] = useState('eng')

  const languages = [['English', 'eng'], ['Suomi', 'fin']]

  const onSubmit = async (event) => {
    event.preventDefault()

    const htmlText = await parseDependencies({ text, language })

    if (!htmlText) {
      alert('Error parsing text. Please check the input and try again.')
      return
    }

    setText('') // Clear input field after submission

    const newTab = window.open('', '_blank')
    if (newTab) {
      newTab.document.open()
      newTab.document.write(htmlText)
      newTab.document.close()
    } else {
      alert('Pop-up blocked! Please allow pop-ups for this site.')
    }
  }

  return (
    <div className='dependencyParsingFormDiv'>
      <h2>Dependency Parsing Tool</h2>
      <form onSubmit={onSubmit}>
        <label htmlFor='textInput'>Text to be parsed:</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Enter here the text to be parsed. Pay attention to sentence syntax and punctuation."
          id='textInput'
          className='textInput'
          rows={8}
          style={{ width: '100%' }}
        />
        <label htmlFor='languageInput'>Language:</label>
        <select
          id='languageInput'
          className='languageInput'
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          {languages.map((lang) => (
            <option key={lang[1]} value={lang[1]}>
              {lang[0]}
            </option>
          ))}
        </select>
        <button type='submit' className='submitButton'>Parse</button>
        <p className='infoText'>
          <b>Note:</b> The text will be parsed and the results will be displayed in a new tab.
          Please ensure that the text is well-formed with correct punctuation for best results. <br />
          Also make sure that pop-ups are allowed for this site.
        </p>
      </form>
    </div>
  )
}

export default DependencyParsingForm
