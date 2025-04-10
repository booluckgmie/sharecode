{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 13,
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "4.474\n"
     ]
    }
   ],
   "source": [
    "import requests\n",
    "import pandas as pd\n",
    "\n",
    "# Send the request to the API\n",
    "r = requests.get(\"https://api.bnm.gov.my/public/exchange-rate/\", \n",
    "                 headers={\"Accept\": \"application/vnd.BNM.API.v1+json\"})\n",
    "\n",
    "# Parse the response JSON\n",
    "payload = r.json()\n",
    "\n",
    "# Loop through the data list to find the USD currency\n",
    "for item in payload['data']:\n",
    "    if item['currency_code'] == 'USD':\n",
    "        buying_rate = item['rate']['buying_rate']\n",
    "        break\n",
    "\n",
    "# Display the DataFrame\n",
    "print(buying_rate)\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.11.9"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

<?php

// URL for the API
$url = "https://api.bnm.gov.my/public/exchange-rate/";

// Set headers
$options = [
    "http" => [
        "header" => "Accept: application/vnd.BNM.API.v1+json"
    ]
];

$context = stream_context_create($options);

// Send the request to the API
$response = file_get_contents($url, false, $context);

// Parse the response JSON
$payload = json_decode($response, true);

// Loop through the data list to find the USD currency
$buying_rate = null;
foreach ($payload['data'] as $item) {
    if ($item['currency_code'] === 'USD') {
        $buying_rate = $item['rate']['buying_rate'];
        break;
    }
}

// Display the buying rate
if ($buying_rate !== null) {
    echo "USD Buying Rate: " . $buying_rate;
} else {
    echo "USD rate not found!";
}

?>
