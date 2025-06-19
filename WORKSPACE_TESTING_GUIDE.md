# 🧪 Workspace Agent Testing Guide with LangSmith Studio

This guide walks you through testing your workspace agent in isolation using the dedicated test graph and LangSmith Studio.

## 🎯 **What We've Created**

### **1. Dedicated Test Graph (`workspace_test_graph.py`)**
- **Isolated Testing**: Tests only the workspace agent without other agents
- **Multiple Scenarios**: Supports 6 different test scenarios
- **Interactive Testing**: Parse user input to determine test type
- **Comprehensive Results**: Detailed success/failure reporting

### **2. Test Scenarios Available**
1. **Google Sheets Extraction** - Test Google Sheets API integration
2. **Data Validation** - Test data quality and validation logic
3. **File Discovery** - Test Google Drive file discovery
4. **Workspace Analysis** - Test workspace structure analysis
5. **Data Transformation** - Test data format standardization
6. **Full Workflow** - Run all tests in sequence

## 🚀 **Using LangSmith Studio**

### **Step 1: Start LangSmith Studio**
```bash
# Make sure you're in the media-planner-infra directory
langgraph up
```

This will start the LangGraph server with both graphs available:
- `media_planning_graph` (full multi-agent system)
- `workspace_test_graph` (isolated workspace testing)

### **Step 2: Access Studio**
1. Open your browser to the LangSmith Studio URL (usually `http://localhost:8123`)
2. Select the **`workspace_test_graph`** from the graph dropdown
3. You should see a simple flow: `START → workspace_test → END`

### **Step 3: Test Different Scenarios**

#### **Test Google Sheets Integration**
**Input Message:**
```
Test Google Sheets extraction functionality
```
**Expected:** The agent will attempt to extract data from a sample Google Sheet and show results.

#### **Test Data Validation**
**Input Message:**
```
Test data validation capabilities
```
**Expected:** The agent will validate sample campaign data and show validation scores.

#### **Test File Discovery**
**Input Message:**
```
Test file discovery functionality  
```
**Expected:** The agent will simulate discovering campaign files in Google Drive.

#### **Test Workspace Analysis**
**Input Message:**
```
Test workspace analysis capabilities
```
**Expected:** The agent will analyze workspace structure and provide recommendations.

#### **Test Data Transformation**
**Input Message:**
```
Test data transformation capabilities
```
**Expected:** The agent will transform raw campaign data into standardized format.

#### **Full Workflow Test**
**Input Message:**
```
Run a comprehensive test of all workspace capabilities
```
**Expected:** The agent will run all tests in sequence and provide a summary.

## 🔍 **Monitoring & Debugging**

### **In LangSmith Studio:**
1. **View State Changes**: Watch how the `CampaignPlanningState` evolves
2. **Monitor Agent Activity**: See detailed logs from workspace tools
3. **Inspect Messages**: View all input/output messages with metadata
4. **Debug Errors**: Get stack traces and error details for failed tests

### **Key State Fields to Monitor:**
- `workspace_data.google_sheets_data` - Extracted Google Sheets data
- `workspace_data.validation_results` - Data validation outcomes
- `workspace_data.extraction_errors` - Any errors encountered
- `current_stage` - Workflow progress (should go from `WORKSPACE_ANALYSIS` to `COMPLETE`)

## 🧪 **Local Testing (Alternative)**

If you want to test without LangSmith Studio:

```bash
# Run the test script
python test_workspace_graph.py
```

This will run all 5 test scenarios automatically and show results.

## 🔧 **Customizing Tests**

### **Add Your Own Test Scenarios**

Edit `workspace_test_graph.py` and:

1. **Add new scenario detection** in `_parse_test_scenario()`:
```python
elif "custom" in instruction_lower:
    return "my_custom_test"
```

2. **Add test implementation** in `_execute_workspace_test()`:
```python
elif scenario == "my_custom_test":
    return await self._test_my_custom_scenario(state)
```

3. **Implement the test method**:
```python
async def _test_my_custom_scenario(self, state):
    # Your test logic here
    task = {"type": "my_task", "data": {...}}
    result = await self.workspace_agent.process_task(state, task)
    return {"success": True, "scenario": "my_custom_test", ...}
```

### **Test with Real Google APIs**

To test with real Google Sheets:

1. **Set up Google credentials** in your `.env` file:
```env
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
```

2. **Replace test spreadsheet ID** in `_test_google_sheets_extraction()`:
```python
task = {
    "type": "extract_google_sheets",
    "data": {
        "spreadsheet_id": "your_real_spreadsheet_id",
        "range": "Sheet1!A1:Z100"
    }
}
```

## 📊 **Understanding Test Results**

### **Success Response Format:**
```
✅ **Workspace Agent Test: Google_Sheets_Extraction**

**Status:** PASSED
**Message:** Google Sheets extraction test completed successfully

**Details:**
- extracted: True
- command_result: Command(goto='planning_agent', ...)
- next_agent: planning_agent
```

### **Failure Response Format:**
```
❌ **Workspace Agent Test: Google_Sheets_Extraction**

**Status:** FAILED  
**Message:** Google Sheets extraction test failed: Authentication required

**Errors:**
- Google API authentication required. Please authenticate first.
```

## 🐛 **Common Issues & Solutions**

### **1. Authentication Warnings**
```
WARNING: Google client secrets file not found
```
**Solution:** This is expected for testing. The agent will use mock data.

### **2. OpenAI API Key Missing**
```
ERROR: OpenAI API key required
```
**Solution:** The test graph sets a mock key automatically, but check your `.env` file.

### **3. Import Errors**
```
ModuleNotFoundError: No module named 'app.services...'
```
**Solution:** Make sure you're running from the `media-planner-infra` directory.

### **4. Graph Not Found in Studio**
**Solution:** Check that `langgraph.json` includes the workspace test graph and restart `langgraph up`.

## 🎯 **Testing Best Practices**

1. **Start Simple**: Test one scenario at a time before running full workflow
2. **Monitor State**: Watch how workspace_data fields get populated
3. **Check Logs**: Use the Studio logs to debug issues
4. **Test Incrementally**: Add your own test scenarios gradually
5. **Mock vs Real**: Start with mocked data, then gradually add real API calls

## 🔄 **Next Steps**

Once workspace agent testing is complete:

1. **Integration Testing**: Test how workspace data flows to planning agent
2. **Performance Testing**: Measure response times and resource usage
3. **Error Scenarios**: Test edge cases and failure modes
4. **Real Data Testing**: Connect to your actual Google Sheets and Drive

---

## 📚 **LangGraph Documentation References**

- [LangGraph State Management](https://python.langchain.com/docs/langgraph)
- [LangSmith Studio Debugging](https://docs.smith.langchain.com/)
- [Multi-Agent Testing Patterns](https://python.langchain.com/docs/langgraph/tutorials/multi_agent/)

Happy Testing! 🚀 