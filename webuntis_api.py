from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime

class WebUntisRoomScraper:
    def __init__(self, school="katharineum", headless=True):
        self.school = school
        self.base_url = f"https://{school}.webuntis.com/WebUntis/monitor?school={school}&monitorType=dayoverview&format=Raumpl%C3%A4ne"
        self.driver = None
        self.headless = headless
        
    def start_browser(self):
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def close_browser(self):
        if self.driver:
            self.driver.quit()
    
    def fetch_room_data(self, room_filter=None, wait_time=15):
        if not self.driver:
            self.start_browser()
        
        try:
            self.driver.get(self.base_url)
            
            WebDriverWait(self.driver, wait_time).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(5)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            return self._parse_room_data(soup, room_filter)
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None
    
    def _parse_room_data(self, soup, room_filter=None):
        if isinstance(room_filter, str):
            room_filter = [room_filter]
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'date': self._extract_date(soup),
            'rooms': {}
        }
        
        table = soup.find('table', class_='dayoverview')
        if not table:
            return result
        
        time_slots = self._extract_time_slots(table)
        tbody = table.find('tbody')
        if not tbody:
            return result
        
        for row in tbody.find_all('tr'):
            header_cell = row.find('th', class_='row-header')
            if not header_cell:
                continue
            
            room_name = header_cell.get_text(strip=True)
            
            if room_filter and room_name.lower() not in [r.lower() for r in room_filter]:
                continue
            
            lessons = self._extract_lessons_from_row(row, time_slots)
            
            if room_name and lessons:
                result['rooms'][room_name] = {
                    'name': room_name,
                    'lessons': lessons,
                    'count': len(lessons)
                }
        
        result['available_rooms'] = list(result['rooms'].keys())
        result['total_rooms'] = len(result['rooms'])
        
        return result
    
    def _extract_date(self, soup):
        h1 = soup.find('h1')
        return h1.get_text(strip=True) if h1 else datetime.now().strftime('%Y-%m-%d')
    
    def _extract_time_slots(self, table):
        thead = table.find('thead')
        if not thead:
            return []
        
        return [cell.get_text(strip=True) for cell in thead.find_all('th', class_='col-header')]
    
    def _extract_lessons_from_row(self, row, time_slots):
        lessons = []
        cells = row.find_all('td')
        
        for i, cell in enumerate(cells):
            period_divs = cell.find_all('div', class_='dayoverview-period')
            if not period_divs:
                continue
            
            time_slot = time_slots[i] if i < len(time_slots) else f"Slot {i+1}"
            
            for period in period_divs:
                left_divs = period.find_all('div', class_='dayoverview-period-left')
                right_divs = period.find_all('div', class_='dayoverview-period-right')
                
                subject = left_divs[0].get_text(strip=True) if left_divs and 'emph' in left_divs[0].get('class', []) else ""
                teacher = left_divs[1].get_text(strip=True) if len(left_divs) > 1 else ""
                class_name = right_divs[0].get_text(strip=True) if right_divs else ""
                
                is_cancelled = 'dayoverview-period-cancelled' in period.get('class', [])
                is_irregular = 'dayoverview-period-irregular' in period.get('class', [])
                
                if class_name or subject or teacher:
                    lessons.append({
                        'time': time_slot,
                        'class': class_name,
                        'subject': subject,
                        'teacher': teacher,
                        'status': 'cancelled' if is_cancelled else 'changed' if is_irregular else 'normal'
                    })
        
        return lessons
    
    def get_all_rooms(self):
        data = self.fetch_room_data()
        return data.get('available_rooms', []) if data else []
    
    def monitor_room(self, room_name="Aul", interval=60):
        try:
            self.start_browser()
            
            while True:
                data = self.fetch_room_data(room_filter=room_name)
                
                if data and room_name in data.get('rooms', {}):
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {room_name}")
                    print(json.dumps(data['rooms'][room_name], indent=2, ensure_ascii=False))
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.close_browser()
    
    def save_json(self, data, filename="room_data.json"):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    scraper = WebUntisRoomScraper(headless=True)
    
    try:
        print("Fetching all rooms...")
        rooms = scraper.get_all_rooms()
        print(f"Found {len(rooms)} rooms: {', '.join(rooms[:10])}")
        
        print("\nFetching room data...")
        all_rooms = scraper.fetch_room_data()
        if all_rooms:
            scraper.save_json(all_rooms, "data.json")
            print(json.dumps(all_rooms, indent=2, ensure_ascii=False))
        
    finally:
        scraper.close_browser()


if __name__ == "__main__":
    main()