# DFFML model_name Models

## About

model_name models.

## Demo

![Demo](https://github.com/intel/dffml/raw/master/docs/images/model_demo.gif)

## Usage

```console
wget http://download.tensorflow.org/data/iris_training.csv
wget http://download.tensorflow.org/data/iris_test.csv
head iris_training.csv
sed -i 's/.*setosa,versicolor,virginica/SepalLength,SepalWidth,PetalLength,PetalWidth,classification/g' *.csv
head iris_training.csv
dffml train \
  -model model_name \
  -model-location tempdir \
  -sources csv=iris_training.csv \
  -classifications 0 1 2 \
  -model-features \
    SepalLength:float:1 \
    SepalWidth:float:1 \
    PetalLength:float:1 \
    PetalWidth:float:1 \
  -epochs 3000 \
  -steps 20000 \
  -log debug
dffml accuracy \
  -model model_name \
  -model-location tempdir \
  -sources csv=iris_training.csv \
  -classifications 0 1 2 \
  -features label:int:1 \
  -model-features \
    SepalLength:float:1 \
    SepalWidth:float:1 \
    PetalLength:float:1 \
    PetalWidth:float:1 \
  -log critical
dffml predict all \
  -model model_name \
  -model-location tempdir \
  -sources csv=iris_test.csv \
  -classifications 0 1 2 \
  -model-features \
    SepalLength:float:1 \
    SepalWidth:float:1 \
    PetalLength:float:1 \
    PetalWidth:float:1 \
  -caching \
  -log critical \
  > results.json
head -n 33 results.json
```

## License

model_name Models are distributed under the terms of the
[MIT License](LICENSE).
