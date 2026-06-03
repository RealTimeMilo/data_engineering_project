# Fetch public subnets
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

# Link the RDS subnet group to the public subnets
resource "aws_db_subnet_group" "feature_store" {
  name       = "feature-store-subnets"
  subnet_ids = data.aws_subnets.public.ids

  tags = {
    Name = "Feature Store Subnet Group"
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "feature-store-rds-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "feature-store-rds-sg" }
}

# 🗄️ RDS PostgreSQL Instance
resource "aws_db_instance" "feature_store" {
  identifier              = "feature-store-practice"
  engine                  = "postgres"
  engine_version          = "16.14"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  storage_type            = "gp3"
  db_name                 = "featurestore"
  username                = "fs_admin"
  password                = "miloisthebest"
  db_subnet_group_name   = aws_db_subnet_group.feature_store.name
  vpc_security_group_ids = [aws_security_group.rds.id]   
  skip_final_snapshot     = true
  publicly_accessible     = true
  backup_retention_period = 1

  tags = {
    Name        = "FeatureStore-Blue"
    Environment = "practice"
    Role        = "blue"
  }
}

# feature-store-practice.cr6um202gaa1.us-east-2.rds.amazonaws.com:5432

# fs_admin

# psql -h feature-store-practice.cr6um202gaa1.us-east-2.rds.amazonaws.com -U fs_admin -d featurestore