import pg from "pg";

const pool = new pg.Pool({
  user: "hermes",
  host: "localhost",
  port: 5432,
  database: "thai_car_intelligence",
  max: 10,
});

export default pool;
