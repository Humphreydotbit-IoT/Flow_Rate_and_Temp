# Ultrasonic Flowmeter Data Collection System

A Docker-based system for collecting and storing data from ultrasonic flowmeters and temperature sensors using Python and Supabase.

## Features

- **Real-time Data Collection**: Continuously reads data from ultrasonic flowmeter and temperature sensors
- **Dual Sensor Support**: 
  - Flowmeter data (flow rate, velocity) via `/dev/ttyUSB0`
  - Temperature data (T1, T2) via `/dev/ttyUSB1`
- **Supabase Integration**: Automatic data storage with real-time synchronization
- **Docker Containerization**: Easy deployment and management
- **Configurable Intervals**: Adjustable reading frequencies for different sensors
- **Data Validation**: Temperature range validation (10-100°C) for accurate readings

## Prerequisites

- Docker and Docker Compose installed
- Supabase account and project
- USB-to-Serial adapters connected to `/dev/ttyUSB0` and `/dev/ttyUSB1`
- Python 3.11+ (for local development)

## Setup

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# Serial Port Configuration (optional - defaults shown)
SERIAL_PORT=/dev/ttyUSB0
SERIAL_PORT_TEMP=/dev/ttyUSB1
BAUD_RATE=9600
BAUD_RATE_TEMP=9600
BUFFER_SIZE=1000
```

### 2. Supabase Database Setup

Create the following tables in your Supabase project:

#### Flow Data Table
```sql
CREATE TABLE flow_data (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    flow DOUBLE PRECISION NOT NULL,
    velocity DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Temperature Data Table
```sql
CREATE TABLE temperature_data (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    t1 DOUBLE PRECISION NOT NULL,
    t2 DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Enable Row Level Security (RLS)
```sql
-- Enable RLS
ALTER TABLE flow_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE temperature_data ENABLE ROW LEVEL SECURITY;

-- Allow all operations for all users
CREATE POLICY "Allow all operations on flow_data" ON flow_data FOR ALL USING (true);
CREATE POLICY "Allow all operations on temperature_data" ON temperature_data FOR ALL USING (true);
```

### 3. Run with Docker Compose

```bash
# Build and start all services
sudo docker compose up --build

# Run in background
sudo docker compose up -d --build

# View logs
sudo docker compose logs -f flow_reader
sudo docker compose logs -f temp_reader

# Stop services
sudo docker compose down
```

## Configuration

### Reading Intervals

- **Flowmeter**: Continuous reading (data collected when available)
- **Temperature**: Every 15 minutes (configurable in `read_and_store_temp.py`)

To change the temperature reading interval, modify the `READ_INTERVAL` variable in `read_and_store_temp.py`:

```python
READ_INTERVAL = 900  # 15 minutes in seconds
```

### Serial Port Configuration

The system automatically detects and uses:
- `/dev/ttyUSB0` for flowmeter data
- `/dev/ttyUSB1` for temperature data

Ensure your USB-to-Serial adapters are properly connected and have the correct permissions.

## Data Format

### Flow Data
- **timestamp**: ISO 8601 UTC format
- **flow**: Flow rate in liters per second (l/s)
- **velocity**: Velocity in meters per second (m/s)

### Temperature Data
- **timestamp**: ISO 8601 UTC format
- **t1**: Temperature 1 in Celsius (°C)
- **t2**: Temperature 2 in Celsius (°C)

## Troubleshooting

### No Data in Logs
1. Check if serial devices are accessible:
   ```bash
   ls -l /dev/ttyUSB*
   ```
2. Verify device permissions:
   ```bash
   sudo chmod 666 /dev/ttyUSB0 /dev/ttyUSB1
   ```
3. Check container logs:
   ```bash
   sudo docker compose logs -f
   ```

### Supabase Connection Issues
1. Verify environment variables are set correctly
2. Check Supabase project URL and API key
3. Ensure RLS policies are configured properly

### Temperature Data Validation
The system only uploads temperature data when both T1 and T2 are between 10-100°C. Out-of-range values are logged but not stored.

## Development

### Local Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run scripts directly
python read_and_store.py
python read_and_store_temp.py
```

### Project Structure

```
ultrasonic-flowmeter/
├── read_and_store.py          # Flowmeter data collection
├── read_and_store_temp.py     # Temperature data collection
├── docker-compose.yml         # Docker services configuration
├── Dockerfile                 # Python environment setup
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (create this)
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## License

This project is open source and available under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions, please create an issue in the GitHub repository. 