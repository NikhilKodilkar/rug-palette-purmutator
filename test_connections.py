import requests
import sys
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from colorama import init, Fore, Style

init()  # Initialize colorama for Windows

@dataclass
class TestResult:
    name: str
    success: bool
    message: str
    details: Optional[Dict] = None

def print_result(result: TestResult) -> None:
    color = Fore.GREEN if result.success else Fore.RED
    status = "✓" if result.success else "✗"
    print(f"{color}{status} {result.name}{Style.RESET_ALL}")
    if not result.success:
        print(f"  {Fore.RED}Error: {result.message}{Style.RESET_ALL}")
    if result.details:
        print(f"  Details: {json.dumps(result.details, indent=2)}")
    print()

def test_frontend() -> TestResult:
    """Test if frontend is accessible"""
    try:
        response = requests.get("http://localhost:5173")
        return TestResult(
            name="Frontend Connection Test",
            success=response.status_code == 200,
            message="Frontend is running and accessible",
            details={"status_code": response.status_code}
        )
    except requests.exceptions.ConnectionError as e:
        return TestResult(
            name="Frontend Connection Test",
            success=False,
            message=f"Could not connect to frontend: {str(e)}"
        )

def test_api() -> TestResult:
    """Test if API is accessible"""
    try:
        response = requests.get("http://localhost:3001/health")
        return TestResult(
            name="API Health Check",
            success=response.status_code == 200,
            message="API is running and accessible",
            details={"status_code": response.status_code, "response": response.json()}
        )
    except requests.exceptions.ConnectionError as e:
        return TestResult(
            name="API Health Check",
            success=False,
            message=f"Could not connect to API: {str(e)}"
        )

def test_cv_service() -> TestResult:
    """Test if CV service is accessible"""
    try:
        response = requests.get("http://127.0.0.1:8000")
        return TestResult(
            name="CV Service Health Check",
            success=response.status_code == 200,
            message="CV Service is running and accessible",
            details={"status_code": response.status_code, "response": response.json()}
        )
    except requests.exceptions.ConnectionError as e:
        return TestResult(
            name="CV Service Health Check",
            success=False,
            message=f"Could not connect to CV Service: {str(e)}"
        )

def test_api_to_cv_connection() -> TestResult:
    """Test if API can connect to CV service"""
    try:
        # First check if API is running
        api_health = requests.get("http://localhost:3001/health")
        if api_health.status_code != 200:
            return TestResult(
                name="API to CV Service Connection Test",
                success=False,
                message="API is not running"
            )
        
        # Try to upload a test image to trigger CV service connection
        test_file = {
            'rugImage': ('test.jpg', open('test_assets/test.jpg', 'rb'), 'image/jpeg')
        }
        response = requests.post("http://localhost:3001/upload", files=test_file)
        
        return TestResult(
            name="API to CV Service Connection Test",
            success=response.status_code in [200, 201],
            message="API successfully connected to CV service",
            details={"status_code": response.status_code, "response": response.json()}
        )
    except FileNotFoundError:
        return TestResult(
            name="API to CV Service Connection Test",
            success=False,
            message="Test image file not found. Please create test_assets/test.jpg"
        )
    except requests.exceptions.ConnectionError as e:
        return TestResult(
            name="API to CV Service Connection Test",
            success=False,
            message=f"Connection failed: {str(e)}"
        )

def main() -> None:
    print(f"{Style.BRIGHT}Running Connection Tests{Style.RESET_ALL}\n")
    
    tests: List[TestResult] = [
        test_frontend(),
        test_api(),
        test_cv_service(),
        test_api_to_cv_connection()
    ]
    
    # Print each test result
    for test in tests:
        print_result(test)
    
    # Print summary
    total = len(tests)
    passed = sum(1 for test in tests if test.success)
    
    print(f"\n{Style.BRIGHT}Test Summary:{Style.RESET_ALL}")
    print(f"Total Tests: {total}")
    print(f"Passed: {Fore.GREEN}{passed}{Style.RESET_ALL}")
    print(f"Failed: {Fore.RED}{total - passed}{Style.RESET_ALL}")
    
    if total - passed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main() 